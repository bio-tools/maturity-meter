"""Ingestion service: collect external metadata for an evaluation request.

Builds the ingestors that apply to a request and runs them concurrently. The
repository is mandatory, so its failure propagates; optional sources degrade
to ``None`` with a warning so one unavailable service does not block an
evaluation.
"""

import asyncio
import logging
from collections.abc import Awaitable, Callable
from typing import Any

import httpx

from maturity_meter.config import get_settings
from maturity_meter.external import (
    BiotoolsIngestor,
    CodeMetricsError,
    CodeMetricsIngestor,
    EDAMIngestor,
    EuropePMCIngestor,
    EuropePMCNotFoundError,
    GitHubIngestor,
    GitLabIngestor,
    OpenAlexIngestor,
    OpenEBenchIngestor,
    ResquiError,
    ResquiIngestor,
    RSEcIngestor,
    formats_in_biotools,
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
    except (
        httpx.HTTPError,
        EuropePMCNotFoundError,
        ResquiError,
        CodeMetricsError,
    ) as error:
        logger.warning(f"Skipping {source}: {error}")
        return None


def _github_token() -> str | None:
    token = get_settings().github_token
    return token.get_secret_value() if token else None


async def _none() -> None:
    return None


async def _given[T](value: T) -> T:
    return value


def _supplied_or[T](
    value: T | None, fetch: Callable[[], Awaitable[T | None]]
) -> Awaitable[T | None]:
    """Use the supplied value if there is one, otherwise fetch it."""
    return _given(value) if value is not None else fetch()


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
    # Supplied data is used as-is; everything missing is fetched.
    supplied = request.data
    biotools_id = request.biotools_id
    # The repository is mandatory, so it is never None once ingested.
    repository_task: Awaitable[dict[str, Any]] = (
        _given(supplied.repository)
        if supplied.repository is not None
        else repository_ingestor(request).fetch()
    )
    biotools = _supplied_or(
        supplied.biotools,
        lambda: (
            _optional("bio.tools", BiotoolsIngestor(biotools_id).fetch())
            if biotools_id
            else _none()
        ),
    )
    # OpenEBench is looked up by bio.tools ID, so it needs one.
    openebench = _supplied_or(
        supplied.openebench,
        lambda: (
            _optional("OpenEBench", OpenEBenchIngestor(biotools_id).fetch())
            if biotools_id
            else _none()
        ),
    )
    # resqui clones the repository and runs Docker checks, so it is by far the
    # slowest source. It only supports GitHub, and degrades to None on failure.
    quality = _supplied_or(
        supplied.quality_checks,
        lambda: (
            _optional(
                "resqui", ResquiIngestor(request.repository, _github_token()).fetch()
            )
            if request.host == "github.com"
            else _none()
        ),
    )
    # RSEc is looked up by bio.tools ID, so it needs one.
    rsec = _supplied_or(
        supplied.rsec,
        lambda: (
            _optional("RSEc", RSEcIngestor(biotools_id).fetch())
            if biotools_id
            else _none()
        ),
    )
    # Code metrics shallow-clone the repository, so they take a while.
    code_metrics = _supplied_or(
        supplied.code_metrics,
        lambda: _optional(
            "code metrics", CodeMetricsIngestor(request.repository).fetch()
        ),
    )
    # Per-DOI sources: only DOIs without a supplied record are fetched.
    missing_pmc = [doi for doi in request.dois if doi not in supplied.europe_pmc]
    europe_pmc = [
        _optional(f"Europe PMC {doi}", EuropePMCIngestor(doi=doi).fetch())
        for doi in missing_pmc
    ]
    # OpenAlex handles missing DOIs itself, mapping them to None.
    missing_oa = [doi for doi in request.dois if doi not in supplied.openalex]
    openalex = OpenAlexIngestor(missing_oa).fetch() if missing_oa else _none()

    try:
        # The repository is gathered on its own so its type stays exact; the
        # optional sources still run concurrently with it.
        repository, optional_sources = await asyncio.gather(
            repository_task,
            asyncio.gather(
                biotools,
                openebench,
                openalex,
                quality,
                rsec,
                code_metrics,
                *europe_pmc,
            ),
        )
        (
            biotools_data,
            openebench_data,
            openalex_data,
            quality_data,
            rsec_data,
            code_metrics_data,
            *europe_pmc_data,
        ) = optional_sources
    except (httpx.HTTPError, ValueError) as error:
        raise _repository_error(request, error) from error

    # EDAM terms describe the bio.tools entry's formats, so they need it first.
    # As with DOIs, only formats without a supplied term are looked up.
    missing_edam = [
        iri for iri in formats_in_biotools(biotools_data) if iri not in supplied.edam
    ]
    edam_data = (
        await _optional("EDAM", EDAMIngestor(missing_edam).fetch())
        if missing_edam
        else None
    )
    return IngestedData(
        request=request,
        repository=repository,
        biotools=biotools_data,
        openebench=openebench_data,
        quality_checks=quality_data,
        rsec=rsec_data,
        code_metrics=code_metrics_data,
        europe_pmc={
            **dict(zip(missing_pmc, europe_pmc_data, strict=True)),
            **supplied.europe_pmc,
        },
        openalex={**(openalex_data or {}), **supplied.openalex},
        edam={**(edam_data or {}), **supplied.edam},
    )
