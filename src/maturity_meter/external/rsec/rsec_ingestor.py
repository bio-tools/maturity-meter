"""
Async client for the Research Software Ecosystem (RSEc) content repository.
Lists the metadata files RSEc holds for a tool, which show where it is
packaged or deployed (Bioconda, Debian Med, BioContainers, Galaxy, ...).
"""

import logging
from typing import Any

import httpx

from maturity_meter.external.github.github_auth import get_github_headers
from maturity_meter.external.protocols import Ingestor

logger = logging.getLogger(__name__)

# RSEc content lives on GitHub, one folder per bio.tools ID under data/.
RSEC_CONTENTS_URL = (
    "https://api.github.com/repos/research-software-ecosystem/content/contents/data"
)
HTTP_TIMEOUT_SECONDS = 15


class RSEcIngestor(Ingestor):
    """
    Ingest the list of RSEc metadata files for a tool.

    Parameters
    ----------
    biotools_id : str
        The bio.tools identifier of the tool (RSEc folders use it, lowercased).
    """

    def __init__(self, biotools_id: str):
        self.biotools_id = biotools_id.lower()

    async def fetch(self) -> dict[str, Any]:
        """
        Fetch the names of the tool's RSEc metadata files.

        Returns
        -------
        dict
            ``{"files": [<file name>, ...]}``. File names identify the
            source, e.g. ``bioconda_<pkg>.yaml``, ``<id>.debian.yaml``,
            ``<id>.biocontainers.yaml`` or ``<id>.galaxy.json``.

        Raises
        ------
        httpx.HTTPStatusError
            With status 404 if RSEc has no folder for the tool.
        """
        url = f"{RSEC_CONTENTS_URL}/{self.biotools_id}"
        try:
            async with httpx.AsyncClient(timeout=HTTP_TIMEOUT_SECONDS) as client:
                resp = await client.get(url, headers=get_github_headers())
                resp.raise_for_status()
                entries = resp.json()
        except httpx.RequestError as e:
            logger.error(f"Network error while fetching {url}: {e}")
            raise
        except httpx.HTTPStatusError as e:
            logger.warning(f"HTTP error {e.response.status_code} from {url}")
            raise
        files = [e["name"] for e in entries if e.get("type") == "file"]
        logger.info(f"Ingested {len(files)} RSEc files for {self.biotools_id}")
        return {"files": files}
