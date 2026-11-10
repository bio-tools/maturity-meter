"""
Async client for the GitHub API.
Fetches a repository and related metadata and returns the raw JSON, plus a few
trimmed lists (files, contributors, closed issues) used by the maturity metrics.
"""

import asyncio
import base64
import logging
from typing import Any

import httpx

from maturity_meter.config import get_settings
from maturity_meter.external.http import get_json, get_json_optional, get_pages
from maturity_meter.external.protocols import Ingestor

logger = logging.getLogger(__name__)


def get_github_headers() -> dict[str, str]:
    """
    Construct headers for GitHub API requests.

    The ``Authorization`` header is only included when a token is configured
    via ``MATURITY_METER_GITHUB_TOKEN``.

    Returns
    -------
    dict
        A dictionary containing the accept header and, if configured, the
        authorization header.
    """
    headers = {"Accept": "application/vnd.github+json"}
    token = get_settings().github_token
    if token is not None:
        headers["Authorization"] = f"Bearer {token.get_secret_value()}"
    return headers


PER_PAGE = 100
# Paginated lists are capped so large projects do not exhaust the rate limit:
# at most this many pages (of PER_PAGE items) per list.
MAX_PAGES = 3
# The API version GitHub recommends for these endpoints.
_VERSION_HEADER = {"X-GitHub-Api-Version": "2022-11-28"}


class GitHubIngestor(Ingestor):
    """
    Ingest GitHub repository metadata via the GitHub REST API (raw JSON).
    """

    def __init__(self, owner: str, repo: str):
        self.api_base = "https://api.github.com"

        self.owner = owner
        self.repo = repo

    @staticmethod
    def _headers(extra: dict[str, str] | None = None) -> dict[str, str]:
        """Auth headers, asking for topics in the repo payload as well."""
        # The mercy preview still matters in practice for topics.
        base = get_github_headers()
        accept = base.get("Accept", "application/vnd.github+json")
        return {
            **base,
            **(extra or {}),
            "Accept": f"{accept}; application/vnd.github.mercy-preview+json",
        }

    @staticmethod
    def _missing(response: httpx.Response) -> bool:
        """Whether an error means GitHub cannot provide the data.

        That covers 404 (missing), 409 (empty repository), 422 and a 403 that
        is not a rate limit (e.g. a contributor list too large to compute).
        Rate limits and other errors still raise.
        """
        rate_limited = response.headers.get("x-ratelimit-remaining") == "0"
        return response.status_code in (404, 409, 422) or (
            response.status_code == 403 and not rate_limited
        )

    async def _get(self, path: str, params: dict[str, Any] | None = None) -> Any:
        url = f"{self.api_base}/repos/{self.owner}/{self.repo}{path}"
        return await get_json(url, params=params, headers=self._headers())

    async def _get_optional(
        self,
        path: str,
        what: str,
        params: dict[str, Any] | None = None,
        *,
        only_404: bool = False,
    ) -> Any:
        """GET a repository path, or None when GitHub cannot provide it."""
        url = f"{self.api_base}/repos/{self.owner}/{self.repo}{path}"
        data = await get_json_optional(
            url,
            params=params,
            headers=self._headers(_VERSION_HEADER),
            missing=(404,) if only_404 else self._missing,
        )
        if data is None:
            logger.info(f"No {what} for {self.owner}/{self.repo}")
        return data

    async def _get_pages(
        self, path: str, what: str, params: dict[str, Any] | None = None
    ) -> list[Any] | None:
        """GET up to MAX_PAGES pages of a list endpoint, or None if unavailable."""
        url = f"{self.api_base}/repos/{self.owner}/{self.repo}{path}"
        data = await get_pages(
            url,
            params=params,
            per_page=PER_PAGE,
            max_pages=MAX_PAGES,
            headers=self._headers(),
            missing=self._missing,
        )
        if data is None:
            logger.info(f"No {what} for {self.owner}/{self.repo}")
        return data

    async def fetch(self) -> dict[str, Any]:
        """
        Fetch the repository and related metadata.

        Returns
        -------
        dict
            The repository record (GET /repos/{owner}/{repo}), latest release,
            GitHub Pages, README, languages, and the trimmed ``files``,
            ``default_branch_protected``, ``contributors``, ``closed_issues``
            and ``open_issues``.
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

    async def fetch_repo(self) -> dict[str, Any]:
        """
        Fetch the full repository object (raw JSON).

        Returns
        -------
        dict
            Raw JSON for the repository from GET /repos/{owner}/{repo}.
        """
        data: dict[str, Any] = await self._get("")
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
        data: dict[str, Any] | None = await self._get_optional(
            "/releases/latest", "releases", only_404=True
        )
        return data

    async def fetch_languages(self) -> dict[str, Any] | None:
        """
        Fetch the programming languages used in the repository.

        Returns
        -------
        dict | None
            Raw JSON for the languages from GET /repos/{owner}/{repo}/languages.
        """
        data: dict[str, Any] | None = await self._get_optional(
            "/languages", "languages", only_404=True
        )
        return data

    async def fetch_github_pages(self) -> dict[str, Any] | None:
        """
        Fetch the GitHub Pages information for the repository.

        Returns
        -------
        dict | None
            Raw JSON for the GitHub Pages from GET /repos/{owner}/{repo}/pages.
        """
        data: dict[str, Any] | None = await self._get_optional(
            "/pages", "GitHub Pages", only_404=True
        )
        return data

    async def fetch_readme(self) -> str | None:
        """
        Fetch the README content (decoded) or return None if not found.

        Returns
        -------
        str | None
            Decoded README content, or None if not found.
        """
        data = await self._get_optional("/readme", "README", only_404=True)
        if data is None:
            return None
        content = base64.b64decode(data.get("content", ""))
        logger.info(f"Ingested README for {self.owner}/{self.repo} successfully")
        return content.decode("utf-8", errors="replace")

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
        data = await self._get_optional(
            f"/git/trees/{branch}", "file tree", {"recursive": "1"}
        )
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
        data = await self._get_optional(f"/branches/{branch}", "branch")
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
        data = await self._get_pages("/contributors", "contributors")
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
        data = await self._get_pages(
            "/issues", "closed issues", {"state": "closed", "sort": "updated"}
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
        query = f"repo:{self.owner}/{self.repo} type:issue state:open"
        data = await get_json_optional(
            f"{self.api_base}/search/issues",
            params={"q": query, "per_page": 1},
            headers=self._headers(),
            missing=self._missing,
        )
        return None if data is None else int(data.get("total_count", 0))

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
        user: dict[str, Any] = await get_json(
            f"{self.api_base}/users/{username}", headers=self._headers()
        )
        return user
