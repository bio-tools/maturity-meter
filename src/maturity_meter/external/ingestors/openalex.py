"""
Async client for the OpenAlex API.
Fetches works by DOI and returns the raw JSON for each.
"""

import asyncio
import logging
from typing import Any

import httpx

from maturity_meter.config import get_settings
from maturity_meter.external.http import get_json_optional
from maturity_meter.external.protocols import Ingestor

logger = logging.getLogger(__name__)

OPENALEX_API_BASE = "https://api.openalex.org"
HTTP_TIMEOUT_SECONDS = 30


class OpenAlexIngestor(Ingestor):
    """
    Ingest publication metadata for one or more DOIs from OpenAlex.

    Parameters
    ----------
    dois : list[str]
        Bare DOIs (e.g. ``"10.1021/acs.jproteome.2c00457"``).
    """

    def __init__(self, dois: list[str]):
        self.dois = dois

    @staticmethod
    def _params() -> dict[str, str]:
        api_key = get_settings().openalex_api_key
        return {"api_key": api_key.get_secret_value()} if api_key else {}

    async def _fetch_single(self, doi: str) -> tuple[str, dict[str, Any] | None]:
        """Fetch one work by DOI; missing or failing works map to None."""
        try:
            work = await get_json_optional(
                f"{OPENALEX_API_BASE}/works/doi:{doi}",
                params=self._params(),
                timeout=HTTP_TIMEOUT_SECONDS,
            )
        except httpx.HTTPError as e:
            logger.warning(f"OpenAlex lookup of DOI {doi} failed: {e}")
            work = None
        return doi, work

    async def fetch(self) -> dict[str, Any]:
        """
        Fetch the OpenAlex work for every DOI concurrently.

        Each DOI is looked up on its own: OpenAlex's batch (list) endpoint is
        served from a separate index that can lag the per-work records by days,
        so it would return different citation counts and FWCI.

        Returns
        -------
        dict
            Mapping of DOI to the raw OpenAlex work JSON, or None when the work
            could not be found or fetched.
        """
        results = dict(
            await asyncio.gather(*(self._fetch_single(doi) for doi in self.dois))
        )
        logger.info(
            f"Ingested {sum(w is not None for w in results.values())} of "
            f"{len(results)} OpenAlex works"
        )
        return results
