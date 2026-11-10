"""Scientific impact metrics.

Each function computes one metric from the ingested data and returns its
:class:`MetricResult`, scored with the placeholder :func:`scale`.
"""

from statistics import mean
from typing import Any

from maturity_meter.components.scaling import scale
from maturity_meter.models import IngestedData, MetricResult

STAR_CAP = 50.0
FORK_CAP = 25.0
CITATION_CAP = 100.0
FWCI_CAP = 2.0

_ADD_DOIS = "Add the DOIs of publications describing the software."


def _repo(data: IngestedData) -> dict[str, Any]:
    """The repository record (GitHub or GitLab)."""
    record: dict[str, Any] = data.repository.get("repo") or {}
    return record


def _works(data: IngestedData) -> list[dict[str, Any]]:
    """OpenAlex works that were found for the request's DOIs."""
    return [work for work in data.openalex.values() if work is not None]


def star_count(data: IngestedData) -> MetricResult:
    """Repository stars, scaled up to STAR_CAP.

    Parameters
    ----------
    data : IngestedData
        Ingested data; uses the GitHub ``stargazers_count`` or the GitLab
        ``star_count`` of the repository record.

    Returns
    -------
    MetricResult
        The scored metric, or ``value=None`` if the count is unavailable.
    """
    repo = _repo(data)
    stars = repo.get("stargazers_count", repo.get("star_count"))
    if stars is None:
        return MetricResult(
            name="star_count", value=None, note="Star count unavailable."
        )
    return MetricResult(
        name="star_count",
        value=scale(stars, cap=STAR_CAP),
        note=f"{stars} stars (scores 1 from {STAR_CAP:g}).",
    )


def fork_count(data: IngestedData) -> MetricResult:
    """Repository forks, scaled up to FORK_CAP.

    Parameters
    ----------
    data : IngestedData
        Ingested data; uses ``forks_count`` of the repository record.

    Returns
    -------
    MetricResult
        The scored metric, or ``value=None`` if the count is unavailable.
    """
    forks = _repo(data).get("forks_count")
    if forks is None:
        return MetricResult(
            name="fork_count", value=None, note="Fork count unavailable."
        )
    return MetricResult(
        name="fork_count",
        value=scale(forks, cap=FORK_CAP),
        note=f"{forks} forks (scores 1 from {FORK_CAP:g}).",
    )


def citation_count(data: IngestedData) -> MetricResult:
    """Citations summed over all publications, scaled up to CITATION_CAP.

    Parameters
    ----------
    data : IngestedData
        Ingested data; uses OpenAlex ``cited_by_count`` of each DOI's work.

    Returns
    -------
    MetricResult
        The scored metric, or ``value=None`` without DOIs or OpenAlex works.
    """
    if not data.request.dois:
        return MetricResult(
            name="citation_count",
            value=None,
            note="No DOIs given.",
            suggestions=[_ADD_DOIS],
        )
    counts = [
        w["cited_by_count"] for w in _works(data) if w.get("cited_by_count") is not None
    ]
    if not counts:
        return MetricResult(
            name="citation_count",
            value=None,
            note="None of the DOIs were found in OpenAlex.",
        )
    total = sum(counts)
    return MetricResult(
        name="citation_count",
        value=scale(total, cap=CITATION_CAP),
        note=(
            f"{total} citations over {len(counts)} publication(s) "
            f"(scores 1 from {CITATION_CAP:g})."
        ),
    )


def fwci(data: IngestedData) -> MetricResult:
    """Field-Weighted Citation Impact, averaged over publications.

    Parameters
    ----------
    data : IngestedData
        Ingested data; uses OpenAlex ``fwci`` of each DOI's work. An FWCI of 1
        means cited as often as the field average.

    Returns
    -------
    MetricResult
        The scored metric (scaled up to FWCI_CAP), or ``value=None``
        without DOIs or FWCI values.
    """
    if not data.request.dois:
        return MetricResult(
            name="fwci", value=None, note="No DOIs given.", suggestions=[_ADD_DOIS]
        )
    values = [w["fwci"] for w in _works(data) if w.get("fwci") is not None]
    if not values:
        return MetricResult(
            name="fwci", value=None, note="OpenAlex has no FWCI for these DOIs."
        )
    average = mean(values)
    return MetricResult(
        name="fwci",
        value=scale(average, cap=FWCI_CAP),
        note=(
            f"Mean FWCI {average:.2f} over {len(values)} publication(s); "
            f"1 is the field average (scores 1 from {FWCI_CAP:g})."
        ),
    )
