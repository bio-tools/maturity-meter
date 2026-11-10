"""
Async client for the OpenAlex API.
Fetches works by DOI and returns the raw JSON for each.
"""

import asyncio
import logging
from typing import Any

import httpx

from maturity_meter.config import get_settings
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

    async def _fetch_doi(
        self, client: httpx.AsyncClient, doi: str
    ) -> tuple[str, dict[str, Any] | None]:
        """Fetch one work, returning None if it is missing or the call fails."""
        url = f"{OPENALEX_API_BASE}/works/doi:{doi}"
        try:
            logger.debug(f"Fetching OpenAlex work: {url}")
            resp = await client.get(url, params=self._params())
            resp.raise_for_status()
            data: dict[str, Any] = resp.json()
            return doi, data
        except httpx.HTTPStatusError as e:
            # One bad DOI should not fail the whole batch.
            logger.warning(
                f"HTTP error {e.response.status_code} from OpenAlex for DOI {doi}"
            )
            return doi, None
        except httpx.RequestError as e:
            logger.warning(f"Network error fetching OpenAlex work for DOI {doi}: {e}")
            return doi, None

    async def fetch(self) -> dict[str, Any]:
        """
        Fetch the OpenAlex work for every DOI concurrently.

        Returns
        -------
        dict
            Mapping of DOI to the raw OpenAlex work JSON, or None when the work
            could not be fetched.
        """
        async with httpx.AsyncClient(timeout=HTTP_TIMEOUT_SECONDS) as client:
            results = await asyncio.gather(
                *(self._fetch_doi(client, doi) for doi in self.dois)
            )
        logger.info(f"Ingested {len(results)} OpenAlex works")
        return dict(results)
