"""
Async client for the Research Software Ecosystem (RSEc) content repository.
Lists the metadata files RSEc holds for a tool, which show where it is
packaged or deployed (Bioconda, Debian Med, BioContainers, Galaxy, ...).
"""

import logging
from typing import Any

from maturity_meter.external.http import get_json
from maturity_meter.external.protocols import Ingestor

from .github import get_github_headers

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
        entries = await get_json(
            url, headers=get_github_headers(), timeout=HTTP_TIMEOUT_SECONDS
        )
        files = [e["name"] for e in entries if e.get("type") == "file"]
        logger.info(f"Ingested {len(files)} RSEc files for {self.biotools_id}")
        return {"files": files}
