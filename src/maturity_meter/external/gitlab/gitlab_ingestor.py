"""
Async client for the GitLab API.
Fetches a project and related metadata and returns the raw JSON.
"""

import logging
from typing import Any
from urllib.parse import quote

import httpx

from maturity_meter.external.protocols import Ingestor

from .gitlab_auth import get_gitlab_headers

logger = logging.getLogger(__name__)


class GitLabIngestor(Ingestor):
    """
    Ingest GitLab project metadata via the GitLab REST API v4 (raw JSON).

    Parameters
    ----------
    owner : str
        Project namespace; may contain subgroups (e.g. ``group/subgroup``).
    repo : str
        Project name.
    host : str, default="gitlab.com"
        GitLab instance hosting the project (gitlab.com or self-hosted).
    """

    def __init__(self, owner: str, repo: str, host: str = "gitlab.com"):
        self.host = host
        self.api_base = f"https://{host}/api/v4"

        self.owner = owner
        self.repo = repo
        # GitLab addresses projects by URL-encoded full path.
        self.project_url = (
            f"{self.api_base}/projects/{quote(f'{owner}/{repo}', safe='')}"
        )

    async def _get(
        self,
        url: str,
        *,
        params: dict[str, Any] | None = None,
    ) -> Any:
        try:
            async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
                resp = await client.get(
                    url, headers=get_gitlab_headers(self.host), params=params
                )
                resp.raise_for_status()
                if resp.headers.get("content-type", "").startswith("application/json"):
                    return resp.json()
                return resp.text
        except httpx.RequestError as e:
            logger.error(f"Network error while fetching {url}: {e}")
            raise
        except httpx.HTTPStatusError as e:
            logger.warning(f"HTTP error {e.response.status_code} from {url}")
            raise

    async def _get_optional(self, url: str, what: str) -> Any | None:
        """GET ``url``, returning None when missing or the feature is disabled."""
        try:
            logger.debug(f"Fetching {what}: {url}")
            return await self._get(url)
        except httpx.HTTPStatusError as e:
            # GitLab answers 403 when a project feature (e.g. releases) is off.
            if e.response.status_code in (403, 404):
                logger.info(f"No {what} for {self.owner}/{self.repo}")
                return None
            raise

    async def fetch(self) -> dict[str, Any]:
        """
        Fetch the project and related metadata.

        Returns
        -------
        dict
            Raw JSON for the project, latest release, README, and languages.
        """
        repo_data = await self.fetch_repo()
        latest_release_data = await self.fetch_latest_release()
        readme = await self.fetch_readme(repo_data)
        languages = await self.fetch_languages()

        result: dict[str, Any] = {
            "repo": repo_data,
            "latest_release": latest_release_data,
            "readme": readme,
            "languages": languages,
        }
        return result

    async def fetch_repo(self) -> dict[str, Any]:
        """
        Fetch the full project object (raw JSON), including its license.

        Returns
        -------
        dict
            Raw JSON for the project from GET /projects/:id.
        """
        logger.debug(f"Fetching project: {self.project_url}")
        data = await self._get(self.project_url, params={"license": "true"})
        if not isinstance(data, dict):
            # Hosts that are not GitLab typically answer with an HTML page.
            raise ValueError(f"{self.host} did not return GitLab API JSON")
        logger.info(f"Ingested data for {self.owner}/{self.repo} successfully")
        return data

    async def fetch_latest_release(self) -> dict[str, Any] | None:
        """
        Fetch the latest release (raw JSON) or return None if there are none.

        Returns
        -------
        dict | None
            Latest release JSON, or None when GitLab returns 404 (no releases).
        """
        url = f"{self.project_url}/releases/permalink/latest"
        data: dict[str, Any] | None = await self._get_optional(url, "releases")
        return data

    async def fetch_languages(self) -> dict[str, Any] | None:
        """
        Fetch the programming languages used in the project.

        Returns
        -------
        dict | None
            Language name to percentage, from GET /projects/:id/languages.
        """
        url = f"{self.project_url}/languages"
        data: dict[str, Any] | None = await self._get_optional(url, "languages")
        return data

    async def fetch_readme(self, repo_data: dict[str, Any] | None = None) -> str | None:
        """
        Fetch the README content or return None if not found.

        Parameters
        ----------
        repo_data : dict, optional
            Project JSON from :meth:`fetch_repo`; fetched when omitted.

        Returns
        -------
        str | None
            README content, or None if not found.
        """
        repo_data = repo_data or await self.fetch_repo()
        readme_url = repo_data.get("readme_url")
        branch = repo_data.get("default_branch")
        if not readme_url or not branch:
            logger.info(f"No README found for {self.owner}/{self.repo}")
            return None
        # readme_url looks like https://<host>/<path>/-/blob/<branch>/<file>
        file_path = readme_url.split(f"/-/blob/{branch}/", 1)[-1]
        url = f"{self.project_url}/repository/files/{quote(file_path, safe='')}/raw"
        try:
            logger.debug(f"Fetching README: {url}")
            content: str = await self._get(url, params={"ref": branch})
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                logger.info(f"No README found for {self.owner}/{self.repo}")
                return None
            raise
        logger.info(f"Ingested README for {self.owner}/{self.repo} successfully")
        return content

    async def get_user(self, username: str) -> dict[str, Any] | None:
        """
        Fetch a GitLab user by username.

        Parameters
        ----------
        username : str
            GitLab username.

        Returns
        -------
        dict | None
            Raw JSON for the user from GET /users?username=..., or None if
            no such user exists.
        """
        users: list[dict[str, Any]] = await self._get(
            f"{self.api_base}/users", params={"username": username}
        )
        return users[0] if users else None
