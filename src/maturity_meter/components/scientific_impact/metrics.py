"""Scientific impact metrics.

Each function computes one metric from the ingested data and returns its
:class:`MetricResult`, scored with the placeholder helpers in
:mod:`maturity_meter.components.utils.scaling`.
"""

from statistics import mean
from typing import Any

from maturity_meter.components.utils.scaling import (
    placeholder_reconcile,
    placeholder_scale,
)
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
        value=placeholder_scale(stars, cap=STAR_CAP),
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
        value=placeholder_scale(forks, cap=FORK_CAP),
        note=f"{forks} forks (scores 1 from {FORK_CAP:g}).",
    )


def _citation_counts(data: IngestedData) -> dict[str, dict[str, int]]:
    """Citation counts per publication and source.

    Publications are keyed by lower-cased DOI so sources can be matched;
    OpenEBench publications without a DOI get a key of their own.

    Returns
    -------
    dict[str, dict[str, int]]
        ``{publication: {source: count}}`` for every source with a count.
    """
    counts: dict[str, dict[str, int]] = {}

    def add(publication: str, source: str, count: Any) -> None:
        if isinstance(count, int | float):
            counts.setdefault(publication.lower(), {})[source] = int(count)

    for doi, work in data.openalex.items():
        if work is not None:
            add(doi, "OpenAlex", work.get("cited_by_count"))
    for doi, record in data.europe_pmc.items():
        if record is not None:
            add(doi, "Europe PMC", record.get("citedByCount"))
    metrics = (data.openebench or {}).get("metrics") or {}
    for publication in (metrics.get("project") or {}).get("publications") or []:
        for entry in publication.get("entries") or []:
            key = (
                entry.get("doi")
                or f"openebench:{entry.get('pmid') or entry.get('title')}"
            )
            add(str(key), "OpenEBench", entry.get("cit_count"))
    return counts


def citation_count(data: IngestedData) -> MetricResult:
    """Citations summed over all publications, scaled up to CITATION_CAP.

    Every source with a count contributes: OpenAlex ``cited_by_count`` and
    Europe PMC ``citedByCount`` for the request's DOIs, and OpenEBench's
    ``cit_count`` for the tool's registered publications. Counts of the same
    publication from different sources are combined with
    :func:`placeholder_reconcile`; the results are summed over publications.

    Parameters
    ----------
    data : IngestedData
        Ingested data.

    Returns
    -------
    MetricResult
        The scored metric, or ``value=None`` if no source has a count.
    """
    counts = _citation_counts(data)
    if not counts:
        if not data.request.dois:
            return MetricResult(
                name="citation_count",
                value=None,
                note="No DOIs given and no publications found in OpenEBench.",
                suggestions=[_ADD_DOIS],
            )
        return MetricResult(
            name="citation_count",
            value=None,
            note="No citation counts found for the publications.",
        )
    per_publication = [
        placeholder_reconcile(list(c.values())) or 0.0 for c in counts.values()
    ]
    total = sum(per_publication)
    sources = sorted({source for c in counts.values() for source in c})
    return MetricResult(
        name="citation_count",
        value=placeholder_scale(total, cap=CITATION_CAP),
        note=(
            f"{total:.0f} citations over {len(counts)} publication(s), "
            f"from {', '.join(sources)} (scores 1 from {CITATION_CAP:g})."
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
        value=placeholder_scale(average, cap=FWCI_CAP),
        note=(
            f"Mean FWCI {average:.2f} over {len(values)} publication(s); "
            f"1 is the field average (scores 1 from {FWCI_CAP:g})."
        ),
    )
