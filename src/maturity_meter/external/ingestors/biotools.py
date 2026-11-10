"""
Async client for the bio.tools API.
Fetches a Tool entry by ID and returns raw JSON consumed by the bio.tools builder.
"""

import logging
from typing import Any

from maturity_meter.external.http import get_json
from maturity_meter.external.protocols import Ingestor

logger = logging.getLogger(__name__)


class BiotoolsIngestor(Ingestor):
    """
    Ingest metadata from bio.tools ID via the bio.tools REST API.

    Parameters
    ----------
    biotools_id : str
        The bio.tools identifier for the tool to fetch.
    """

    def __init__(self, biotools_id: str):
        self.api_base = "https://bio.tools/api"

        self.biotools_id = biotools_id

    async def fetch(self) -> dict[str, Any]:
        """
        Fetch the bio.tools entry for the specified tool ID.

        Returns
        -------
        dict
            JSON metadata for the bio.tools entry.
        """
        logger.debug(f"Fetching bio.tools entry for {self.biotools_id}")
        url = f"{self.api_base}/tool/{self.biotools_id}"
        data: dict[str, Any] = await get_json(
            url, params={"format": "json"}, timeout=10
        )
        if not data.get("name"):
            logger.warning(f"bio.tools entry {self.biotools_id} missing 'name' field")
        logger.info(f"Ingested bio.tools entry for {self.biotools_id} successfully")
        return data
