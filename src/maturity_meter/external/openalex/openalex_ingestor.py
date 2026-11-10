"""
Async client for the OpenAlex API.
Fetches works by DOI and returns the raw JSON for each.
"""

import asyncio
import logging
from typing import Any

import httpx

from maturity_meter.config import get_settings
from maturity_meter.external.http import get_json, get_json_optional
from maturity_meter.external.protocols import Ingestor

logger = logging.getLogger(__name__)

OPENALEX_API_BASE = "https://api.openalex.org"
HTTP_TIMEOUT_SECONDS = 30
# OpenAlex accepts up to 50 values in one OR filter (``doi:a|b|...``).
BATCH_SIZE = 50
_DOI_URL_PREFIX = "https://doi.org/"


def _batchable(doi: str) -> bool:
    """Whether a DOI can go in an OR filter (``|`` and ``,`` are syntax)."""
    return "|" not in doi and "," not in doi


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

    async def _fetch_batch(self, dois: list[str]) -> dict[str, dict[str, Any] | None]:
        """Fetch up to BATCH_SIZE works in one request; failures map to None."""
        found: dict[str, dict[str, Any] | None] = {doi: None for doi in dois}
        params = {
            **self._params(),
            "filter": "doi:" + "|".join(dois),
            "per-page": str(BATCH_SIZE),
        }
        try:
            data = await get_json(
                f"{OPENALEX_API_BASE}/works",
                params=params,
                timeout=HTTP_TIMEOUT_SECONDS,
            )
        except httpx.HTTPError as e:
            # One failing batch should not fail the whole ingestion.
            logger.warning(f"OpenAlex batch of {len(dois)} DOIs failed: {e}")
            return found
        # Works carry their DOI as a lower-cased doi.org URL; DOIs are
        # case-insensitive, so match on the lower-cased bare DOI.
        by_doi = {doi.lower(): doi for doi in dois}
        for work in data.get("results", []):
            key = str(work.get("doi") or "").removeprefix(_DOI_URL_PREFIX).lower()
            if key in by_doi:
                found[by_doi[key]] = work
        return found

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
        Fetch the OpenAlex works for all DOIs, in batches of up to BATCH_SIZE.

        Returns
        -------
        dict
            Mapping of DOI to the raw OpenAlex work JSON, or None when the work
            could not be found or fetched.
        """
        batchable = [doi for doi in self.dois if _batchable(doi)]
        batches = [
            batchable[i : i + BATCH_SIZE] for i in range(0, len(batchable), BATCH_SIZE)
        ]
        singles = [doi for doi in self.dois if not _batchable(doi)]
        batch_results, single_results = await asyncio.gather(
            asyncio.gather(*(self._fetch_batch(batch) for batch in batches)),
            asyncio.gather(*(self._fetch_single(doi) for doi in singles)),
        )
        works: dict[str, Any] = {}
        for result in batch_results:
            works.update(result)
        works.update(dict(single_results))
        # Keep the caller's order.
        ordered = {doi: works.get(doi) for doi in self.dois}
        logger.info(
            f"Ingested {sum(w is not None for w in ordered.values())} of "
            f"{len(ordered)} OpenAlex works"
        )
        return ordered
