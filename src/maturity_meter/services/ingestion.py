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

from maturity_meter.config import get_settings
from maturity_meter.external import (
    BiotoolsIngestor,
    EuropePMCIngestor,
    EuropePMCNotFoundError,
    GitHubIngestor,
    GitLabIngestor,
    OpenAlexIngestor,
    ResquiError,
    ResquiIngestor,
)
from maturity_meter.external.protocols import Ingestor
from maturity_meter.models import EvaluationRequest, IngestedData

logger = logging.getLogger(__name__)

TOKEN_VARIABLES = {
    "github.com": "MATURITY_METER_GITHUB_TOKEN",
    "gitlab.com": "MATURITY_METER_GITLAB_TOKEN",
}


class RepositoryFetchError(Exception):
    """The mandatory repository could not be fetched.

    Parameters
    ----------
    reason : str
        Machine-readable cause: ``not_found``, ``forbidden``, ``rate_limited``,
        ``unreachable`` or ``unsupported``. Adapters map it to their own error
        style.
    message : str
        Human-readable explanation.
    """

    def __init__(self, reason: str, message: str):
        super().__init__(message)
        self.reason = reason


def _repository_error(
    request: EvaluationRequest, error: Exception
) -> RepositoryFetchError:
    """Translate a failed repository fetch into a RepositoryFetchError."""
    url = request.repository
    if isinstance(error, httpx.HTTPStatusError):
        response = error.response
        status = response.status_code
        rate_limited = (
            status == 429
            or response.headers.get("x-ratelimit-remaining") == "0"
            or "rate limit" in response.text.lower()
        )
        if rate_limited:
            variable = TOKEN_VARIABLES.get(request.host)
            hint = f" Set {variable} to raise the limit." if variable else ""
            return RepositoryFetchError(
                "rate_limited", f"Rate limited by {request.host}.{hint}"
            )
        if status == 404:
            return RepositoryFetchError(
                "not_found",
                f"Repository not found: {url}. It may not exist or may be private.",
            )
        if status in (401, 403):
            return RepositoryFetchError(
                "forbidden", f"Access to {url} was denied. It may be private."
            )
        return RepositoryFetchError(
            "unreachable", f"{request.host} answered with HTTP {status} for {url}."
        )
    if isinstance(error, httpx.RequestError):
        return RepositoryFetchError(
            "unreachable", f"Could not reach {request.host}: {error}"
        )
    return RepositoryFetchError(
        "unsupported",
        f"{request.host} does not look like GitHub or a GitLab instance.",
    )


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
    except (httpx.HTTPError, EuropePMCNotFoundError, ResquiError) as error:
        logger.warning(f"Skipping {source}: {error}")
        return None


def _github_token() -> str | None:
    token = get_settings().github_token
    return token.get_secret_value() if token else None


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

    Raises
    ------
    RepositoryFetchError
        If the repository cannot be fetched. Failures of optional sources are
        logged and reported as ``None`` instead.
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
    # resqui clones the repository and runs Docker checks, so it is by far the
    # slowest source. It only supports GitHub, and degrades to None on failure.
    quality: Awaitable[dict[str, Any] | None] = (
        _optional("resqui", ResquiIngestor(request.repository, _github_token()).fetch())
        if request.host == "github.com"
        else _none()
    )
    # OpenAlex handles missing DOIs itself, mapping them to None.
    openalex = OpenAlexIngestor(request.dois).fetch() if request.dois else _none()

    try:
        (
            repository,
            biotools_data,
            openalex_data,
            quality_data,
            *europe_pmc_data,
        ) = await asyncio.gather(
            repository_ingestor(request).fetch(),
            biotools,
            openalex,
            quality,
            *europe_pmc,
        )
    except (httpx.HTTPError, ValueError) as error:
        raise _repository_error(request, error) from error
    return IngestedData(
        request=request,
        repository=repository,
        biotools=biotools_data,
        quality_checks=quality_data,
        europe_pmc=dict(zip(request.dois, europe_pmc_data, strict=True)),
        openalex=openalex_data or {},
    )
