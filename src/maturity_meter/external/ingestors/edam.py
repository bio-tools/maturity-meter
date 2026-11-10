"""
Async client for EDAM ontology terms via the EMBL-EBI OLS4 API.
Looks up EDAM terms by IRI, for example to tell whether a data format is a
leaf (specific) format or a broad parent class.
"""

import asyncio
import logging
from typing import Any
from urllib.parse import quote

from maturity_meter.external.http import get_json_optional
from maturity_meter.external.protocols import Ingestor

logger = logging.getLogger(__name__)

OLS4_TERMS_URL = "https://www.ebi.ac.uk/ols4/api/ontologies/edam/terms"
HTTP_TIMEOUT_SECONDS = 15
MAX_CONCURRENT_REQUESTS = 10

# EDAM changes rarely and the same formats recur across tools, so terms are
# cached for the lifetime of the process.
_cache: dict[str, dict[str, Any] | None] = {}


def formats_in_biotools(entry: dict[str, Any] | None) -> list[str]:
    """Return the unique EDAM format IRIs of a bio.tools entry's functions.

    Parameters
    ----------
    entry : dict | None
        Raw bio.tools entry.

    Returns
    -------
    list[str]
        Format IRIs of all function inputs and outputs, in first-seen order.
    """
    iris: dict[str, None] = {}
    for function in (entry or {}).get("function") or []:
        for io in (function.get("input") or []) + (function.get("output") or []):
            for fmt in io.get("format") or []:
                if fmt.get("uri"):
                    iris[fmt["uri"]] = None
    return list(iris)


class EDAMIngestor(Ingestor):
    """
    Look up EDAM terms by IRI.

    Parameters
    ----------
    iris : list[str]
        EDAM term IRIs, e.g. ``"http://edamontology.org/format_2572"``.
    """

    def __init__(self, iris: list[str]):
        self.iris = iris

    async def _fetch_term(
        self, limit: asyncio.Semaphore, iri: str
    ) -> tuple[str, dict[str, Any] | None]:
        """Fetch one term, returning None if OLS4 does not know it."""
        if iri in _cache:
            return iri, _cache[iri]
        # OLS4 expects the IRI double URL-encoded in the path.
        url = f"{OLS4_TERMS_URL}/{quote(quote(iri, safe=''), safe='')}"
        async with limit:
            data = await get_json_optional(url, timeout=HTTP_TIMEOUT_SECONDS)
        if data is None:
            logger.info(f"Unknown EDAM term {iri}")
            term = None
        else:
            term = {
                "label": data.get("label"),
                "has_children": data.get("has_children"),
                "is_obsolete": data.get("is_obsolete"),
            }
        _cache[iri] = term
        return iri, term

    async def fetch(self) -> dict[str, Any]:
        """
        Fetch all terms concurrently.

        Returns
        -------
        dict
            Mapping of IRI to ``{"label", "has_children", "is_obsolete"}``,
            or None for IRIs that OLS4 does not know. A format with
            ``has_children`` False is a leaf (specific) format.

        Raises
        ------
        httpx.HTTPStatusError, httpx.RequestError
            If OLS4 fails for a reason other than an unknown term.
        """
        limit = asyncio.Semaphore(MAX_CONCURRENT_REQUESTS)
        results = await asyncio.gather(
            *(self._fetch_term(limit, iri) for iri in self.iris)
        )
        logger.info(f"Looked up {len(results)} EDAM terms")
        return dict(results)
