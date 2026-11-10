"""
Async client for the Europe PMC API.
Fetches a publication by PMID/PMCID/DOI and returns the first matching record.
Raises EuropePMCNotFoundError if no record is found.
"""

import logging
from typing import Any

from maturity_meter.external.http import get_json
from maturity_meter.external.protocols import Ingestor

logger = logging.getLogger(__name__)

EUROPE_PMC_API_BASE = "https://www.ebi.ac.uk/europepmc/webservices/rest"
HTTP_TIMEOUT_SECONDS = 10


class EuropePMCNotFoundError(Exception):
    """Raised when no Europe PMC record matches the given identifiers."""


class EuropePMCIngestor(Ingestor):
    """
    Ingest a publication record from Europe PMC using one or more identifiers.

    Parameters
    ----------
    pmid : str, optional
        PubMed identifier (e.g., "36173614").
    pmcid : str, optional
        PubMed Central identifier (e.g., "PMC9903320").
    doi : str, optional
        Digital Object Identifier (e.g., "10.1021/acs.jproteome.2c00457").
    """

    def __init__(
        self,
        pmid: str | None = None,
        pmcid: str | None = None,
        doi: str | None = None,
    ):
        if not any([pmid, pmcid, doi]):
            raise ValueError("Provide at least one of: pmid, pmcid, doi.")
        self.pmid = pmid
        self.pmcid = pmcid
        self.doi = doi

    def _build_queries(self) -> list[str]:
        queries: list[str] = []
        if self.pmid:
            queries.append(f"EXT_ID:{self.pmid} AND SRC:MED")
        if self.pmcid:
            queries.append(f"EXT_ID:{self.pmcid} AND SRC:PMC")
        if self.doi:
            # Try both DOI: and EXT_ID:"<doi>" variants
            queries.append(f"DOI:{self.doi}")
            queries.append(f'EXT_ID:"{self.doi}"')
        return queries

    async def _search(self, query: str) -> dict[str, Any]:
        params = {"format": "json", "resultType": "core", "pageSize": 1, "query": query}
        data: dict[str, Any] = await get_json(
            f"{EUROPE_PMC_API_BASE}/search", params=params, timeout=HTTP_TIMEOUT_SECONDS
        )
        return data

    @staticmethod
    def _first_result(payload: dict[str, Any]) -> dict[str, Any] | None:
        results = payload.get("resultList", {}).get("result") or []
        first: dict[str, Any] | None = results[0] if results else None
        return first

    async def fetch(self) -> dict[str, Any]:
        """
        Fetch the Europe PMC record matching the provided identifiers.

        Returns
        -------
        dict
            The first matching Europe PMC record.

        Raises
        ------
        EuropePMCNotFoundError
            If no record matches the provided identifiers.
        httpx.RequestError, httpx.HTTPStatusError
            For network/HTTP issues.
        """
        # All identifier forms name the same publication, so one OR query
        # replaces trying them one after another.
        query = " OR ".join(f"({q})" for q in self._build_queries())
        logger.debug(f"Querying Europe PMC with: {query}")
        rec = self._first_result(await self._search(query))
        if rec:
            logger.info("Found Europe PMC record")
            return rec

        msg = (
            "No Europe PMC record found for identifiers "
            f"pmid={self.pmid!r}, pmcid={self.pmcid!r}, doi={self.doi!r}"
        )
        logger.info(msg)
        raise EuropePMCNotFoundError(msg)
