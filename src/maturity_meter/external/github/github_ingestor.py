"""
Async client for the GitHub API.
Fetches a repository and related metadata and returns the raw JSON, plus a few
trimmed lists (files, contributors, closed issues) used by the maturity metrics.
"""

import asyncio
import logging
from typing import Any

import httpx

from maturity_meter.external.protocols import Ingestor

from .github_auth import get_github_headers

logger = logging.getLogger(__name__)

PER_PAGE = 100
# Paginated lists are capped so large projects do not exhaust the rate limit:
# at most this many pages (of PER_PAGE items) per list.
MAX_PAGES = 3


class GitHubIngestor(Ingestor):
    """
    Ingest GitHub repository metadata via the GitHub REST API (raw JSON).
    """

    def __init__(self, owner: str, repo: str):
        self.api_base = "https://api.github.com"

        self.owner = owner
        self.repo = repo

    async def _get(
        self,
        url: str,
        *,
        params: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> Any:
        # Ask for topics in the repo payload as well
        # (mercy preview still matters in practice).
        base_headers = get_github_headers()
        want_topics = "application/vnd.github.mercy-preview+json"
        accept = base_headers.get("Accept", "application/vnd.github+json")
        merged = {
            **base_headers,
            **(headers or {}),
            "Accept": f"{accept}; {want_topics}",
        }

        try:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.get(url, headers=merged, params=params)
                resp.raise_for_status()
                # 204 No Content, e.g. contributors of an empty repository.
                return None if resp.status_code == 204 else resp.json()
        except httpx.RequestError as e:
            logger.error(f"Network error while fetching {url}: {e}")
            raise
        except httpx.HTTPStatusError as e:
            logger.warning(f"HTTP error {e.response.status_code} from {url}")
            raise

    async def fetch(self) -> dict[str, Any]:
        """
        Fetch the full repository object (single endpoint).

        Returns
        -------
        dict
            Raw JSON for the repository from GET /repos/{owner}/{repo}.
        """
        # The repository record gives the default branch; everything else is
        # independent, so it is requested concurrently afterwards.
        repo_data = await self.fetch_repo()
        branch = repo_data.get("default_branch") or "main"
        (
            latest_release_data,
            github_pages,
            readme,
            languages,
            files,
            branch_protected,
            contributors,
            closed_issues,
            open_issues,
        ) = await asyncio.gather(
            self.fetch_latest_release(),
            self.fetch_github_pages(),
            self.fetch_readme(),
            self.fetch_languages(),
            self.fetch_files(branch),
            self.fetch_default_branch_protected(branch),
            self.fetch_contributors(),
            self.fetch_closed_issues(),
            self.fetch_open_issues(),
        )

        result: dict[str, Any] = {
            "repo": repo_data,
            "latest_release": latest_release_data,
            "github_pages": github_pages,
            "readme": readme,
            "languages": languages,
            "files": files,
            "default_branch_protected": branch_protected,
            "contributors": contributors,
            "closed_issues": closed_issues,
            "open_issues": open_issues,
        }
        return result

    async def _get_optional(
        self, url: str, what: str, params: dict[str, Any] | None = None
    ) -> Any:
        """GET ``url``, returning None when GitHub cannot provide it.

        That covers 404 (missing), 409 (empty repository), 422 and a 403 that
        is not a rate limit (e.g. a contributor list too large to compute).
        Rate limits and other errors still raise.
        """
        try:
            return await self._get(url, params=params)
        except httpx.HTTPStatusError as e:
            response = e.response
            rate_limited = response.headers.get("x-ratelimit-remaining") == "0"
            if response.status_code in (404, 409, 422) or (
                response.status_code == 403 and not rate_limited
            ):
                logger.info(f"No {what} for {self.owner}/{self.repo}")
                return None
            raise

    async def _get_pages(
        self, url: str, what: str, params: dict[str, Any] | None = None
    ) -> list[Any] | None:
        """GET up to MAX_PAGES pages of a list endpoint, or None if unavailable."""
        items: list[Any] = []
        for page in range(1, MAX_PAGES + 1):
            batch = await self._get_optional(
                url, what, {**(params or {}), "per_page": PER_PAGE, "page": page}
            )
            if batch is None:
                return items or None
            items.extend(batch)
            if len(batch) < PER_PAGE:
                break
        return items

    async def fetch_files(self, branch: str) -> list[str] | None:
        """
        Fetch the paths of all files on a branch.

        Parameters
        ----------
        branch : str
            Branch to list, usually the default branch.

        Returns
        -------
        list[str] | None
            File paths from GET /git/trees/{branch}?recursive=1, or None if
            the tree is unavailable (e.g. an empty repository). Very large
            trees may be truncated by GitHub.
        """
        url = f"{self.api_base}/repos/{self.owner}/{self.repo}/git/trees/{branch}"
        data = await self._get_optional(url, "file tree", {"recursive": "1"})
        if data is None:
            return None
        if data.get("truncated"):
            logger.info(f"File tree of {self.owner}/{self.repo} is truncated")
        return [item["path"] for item in data.get("tree", []) if item["type"] == "blob"]

    async def fetch_default_branch_protected(self, branch: str) -> bool | None:
        """
        Fetch whether a branch is protected.

        Parameters
        ----------
        branch : str
            Branch to check, usually the default branch.

        Returns
        -------
        bool | None
            The ``protected`` flag from GET /branches/{branch}, or None.
        """
        url = f"{self.api_base}/repos/{self.owner}/{self.repo}/branches/{branch}"
        data = await self._get_optional(url, "branch")
        return None if data is None else bool(data.get("protected"))

    async def fetch_contributors(self) -> list[dict[str, Any]] | None:
        """
        Fetch contributors and their commit counts.

        Returns
        -------
        list[dict] | None
            ``{"name", "contributions"}`` per contributor, most active first,
            capped at MAX_PAGES * PER_PAGE contributors.
        """
        url = f"{self.api_base}/repos/{self.owner}/{self.repo}/contributors"
        data = await self._get_pages(url, "contributors")
        if data is None:
            return None
        return [
            {"name": c.get("login"), "contributions": c.get("contributions", 0)}
            for c in data
        ]

    async def fetch_closed_issues(self) -> list[dict[str, Any]] | None:
        """
        Fetch the most recently closed issues (pull requests excluded).

        Returns
        -------
        list[dict] | None
            ``{"created_at", "closed_at"}`` per issue, from at most
            MAX_PAGES * PER_PAGE recently closed issues and pull requests.
        """
        url = f"{self.api_base}/repos/{self.owner}/{self.repo}/issues"
        data = await self._get_pages(
            url, "closed issues", {"state": "closed", "sort": "updated"}
        )
        if data is None:
            return None
        return [
            {"created_at": i.get("created_at"), "closed_at": i.get("closed_at")}
            for i in data
            if "pull_request" not in i
        ]

    async def fetch_open_issues(self) -> int | None:
        """
        Fetch the number of open issues, excluding pull requests.

        The repository's ``open_issues_count`` includes pull requests, so this
        uses the search API, which has its own, lower rate limit.

        Returns
        -------
        int | None
            Number of open issues, or None if unavailable.
        """
        url = f"{self.api_base}/search/issues"
        query = f"repo:{self.owner}/{self.repo} type:issue state:open"
        data = await self._get_optional(url, "open issues", {"q": query, "per_page": 1})
        return None if data is None else int(data.get("total_count", 0))

    async def fetch_repo(self) -> dict[str, Any]:
        """
        Fetch the full repository object (raw JSON).

        Returns
        -------
        dict
            Raw JSON for the repository from GET /repos/{owner}/{repo}.
        """
        url = f"{self.api_base}/repos/{self.owner}/{self.repo}"
        logger.debug(f"Fetching repository: {url}")
        data: dict[str, Any] = await self._get(url)
        logger.info(f"Ingested data for {self.owner}/{self.repo} successfully")
        return data

    async def fetch_latest_release(self) -> dict[str, Any] | None:
        """
        Fetch the latest release (raw JSON) or return None if the repo has no releases.

        Returns
        -------
        dict | None
            Latest release JSON, or None when GitHub returns 404 (no releases).
        """
        url = f"{self.api_base}/repos/{self.owner}/{self.repo}/releases/latest"
        # Include the version header GitHub recommends;
        # Accept is already set in get_github_headers().
        headers = {"X-GitHub-Api-Version": "2022-11-28"}
        try:
            logger.debug(f"Fetching latest release: {url}")
            data: dict[str, Any] = await self._get(url, headers=headers)
            return data
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                logger.info(f"No releases for {self.owner}/{self.repo}")
                return None
            raise

    async def fetch_languages(self) -> dict[str, Any] | None:
        """
        Fetch the programming languages used in the repository.

        Returns
        -------
        dict | None
            Raw JSON for the languages from GET /repos/{owner}/{repo}/languages.
        """
        url = f"{self.api_base}/repos/{self.owner}/{self.repo}/languages"
        headers = {"X-GitHub-Api-Version": "2022-11-28"}
        try:
            logger.debug(f"Fetching languages: {url}")
            data: dict[str, Any] = await self._get(url, headers=headers)
            return data
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                logger.info(f"No languages found for {self.owner}/{self.repo}")
                return None
            raise

    async def fetch_github_pages(self) -> dict[str, Any] | None:
        """
        Fetch the GitHub Pages information for the repository.

        Returns
        -------
        dict
            Raw JSON for the GitHub Pages from GET /repos/{owner}/{repo}/pages.
        """
        url = f"{self.api_base}/repos/{self.owner}/{self.repo}/pages"
        headers = {"X-GitHub-Api-Version": "2022-11-28"}
        try:
            logger.debug(f"Fetching GitHub pages: {url}")
            data: dict[str, Any] = await self._get(url, headers=headers)
            return data
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                logger.info(f"No GitHub pages found for {self.owner}/{self.repo}")
                return None
            raise

    async def fetch_readme(self) -> str | None:
        """
        Fetch the README content (decoded) or return None if not found.

        Returns
        -------
        str | None
            Decoded README content, or None if not found.
        """
        url = f"{self.api_base}/repos/{self.owner}/{self.repo}/readme"
        headers = {"X-GitHub-Api-Version": "2022-11-28"}
        try:
            logger.debug(f"Fetching README: {url}")
            data = await self._get(url, headers=headers)
            import base64

            content_encoded = data.get("content", "")
            content_bytes = base64.b64decode(content_encoded)
            content_str = content_bytes.decode("utf-8", errors="replace")
            logger.info(f"Ingested README for {self.owner}/{self.repo} successfully")
            return content_str
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                logger.info(f"No README found for {self.owner}/{self.repo}")
                return None
            raise

    async def get_user(self, username: str) -> dict[str, Any]:
        """
        Fetch a GitHub user by username.

        Parameters
        ----------
        username : str
            GitHub username.

        Returns
        -------
        dict
            Raw JSON for the user from GET /users/{username}.
        """
        url = f"{self.api_base}/users/{username}"
        user: dict[str, Any] = await self._get(url)
        return user
