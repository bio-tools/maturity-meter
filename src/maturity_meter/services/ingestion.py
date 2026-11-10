"""Ingestion service: collect external metadata for an evaluation request.

Builds the ingestors that apply to a request and runs them concurrently. The
repository is mandatory, so its failure propagates; optional sources degrade
to ``None`` with a warning so one unavailable service does not block an
evaluation.
"""

import asyncio
import logging
from collections.abc import Awaitable
from typing import Any

import httpx

from maturity_meter.external import (
    BiotoolsIngestor,
    EuropePMCIngestor,
    EuropePMCNotFoundError,
    GitHubIngestor,
    GitLabIngestor,
    OpenAlexIngestor,
)
from maturity_meter.external.protocols import Ingestor
from maturity_meter.models import EvaluationRequest, IngestedData

logger = logging.getLogger(__name__)


def repository_ingestor(request: EvaluationRequest) -> Ingestor:
    """Return the ingestor for the request's hosting platform.

    Parameters
    ----------
    request : EvaluationRequest
        Request whose repository should be ingested.

    Returns
    -------
    Ingestor
        GitHub or GitLab ingestor.

    """
    if request.host == "github.com":
        return GitHubIngestor(request.owner, request.repo)
    # Any other host is assumed to be a GitLab instance (gitlab.com or
    # self-hosted).
    return GitLabIngestor(request.owner, request.repo, request.host)


async def _optional[T](source: str, awaitable: Awaitable[T]) -> T | None:
    """Await an optional source, returning None if it is unavailable."""
    try:
        return await awaitable
    except (httpx.HTTPError, EuropePMCNotFoundError) as error:
        logger.warning(f"Skipping {source}: {error}")
        return None


async def _none() -> None:
    return None


async def ingest(request: EvaluationRequest) -> IngestedData:
    """Fetch all external metadata for ``request`` concurrently.

    Parameters
    ----------
    request : EvaluationRequest
        Repository and optional publication/bio.tools identifiers.

    Returns
    -------
    IngestedData
        Raw metadata from every applicable source.
    """
    logger.debug(f"Ingesting metadata for {request.repository}")
    biotools: Awaitable[dict[str, Any] | None] = (
        _optional("bio.tools", BiotoolsIngestor(request.biotools_id).fetch())
        if request.biotools_id
        else _none()
    )
    europe_pmc = [
        _optional(f"Europe PMC {doi}", EuropePMCIngestor(doi=doi).fetch())
        for doi in request.dois
    ]
    # OpenAlex handles missing DOIs itself, mapping them to None.
    openalex = OpenAlexIngestor(request.dois).fetch() if request.dois else _none()

    repository, biotools_data, openalex_data, *europe_pmc_data = await asyncio.gather(
        repository_ingestor(request).fetch(), biotools, openalex, *europe_pmc
    )
    return IngestedData(
        request=request,
        repository=repository,
        biotools=biotools_data,
        europe_pmc=dict(zip(request.dois, europe_pmc_data, strict=True)),
        openalex=openalex_data or {},
    )
