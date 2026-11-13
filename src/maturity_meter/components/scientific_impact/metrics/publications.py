"""Scientific impact metrics from publications: citations and FWCI."""

from statistics import mean
from typing import Any

from maturity_meter.components.utils.scaling import (
    log_scale,
    placeholder_reconcile,
    ratio_to_average_scale,
)
from maturity_meter.models import IngestedData, MetricResult

# Total citations that score 1 on the log scale (see log_scale): about the
# top 10% of the publications of bio.tools-registered tools (median 19 in
# OpenAlex).
CITATION_REFERENCE = 100.0


_ADD_DOIS = "Add the DOIs of publications describing the software."


def _works(data: IngestedData) -> list[dict[str, Any]]:
    """OpenAlex works that were found for the request's DOIs."""
    return [work for work in data.openalex.values() if work is not None]


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
    for publication in (data.biotools or {}).get("publication") or []:
        key = publication.get("doi") or (
            f"pmid:{publication['pmid']}" if publication.get("pmid") else None
        )
        if key:
            add(
                str(key),
                "bio.tools",
                (publication.get("metadata") or {}).get("citationCount"),
            )
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
    """Citations of the software's publications, on a log scale.

    Every source with a count contributes: OpenAlex ``cited_by_count`` and
    Europe PMC ``citedByCount`` for the request's DOIs, and the bio.tools
    ``citationCount`` and OpenEBench ``cit_count`` of the tool's registered
    publications. Each source's counts are summed over its publications and
    scaled with :func:`log_scale` (1 from CITATION_REFERENCE); the scores of
    the sources are then reconciled with :func:`placeholder_reconcile`.

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
    totals: dict[str, int] = {}
    for per_source in counts.values():
        for source, count in per_source.items():
            totals[source] = totals.get(source, 0) + count
    scores = {
        source: log_scale(total, reference=CITATION_REFERENCE)
        for source, total in totals.items()
    }
    return MetricResult(
        name="citation_count",
        value=placeholder_reconcile(list(scores.values())),
        note=(
            "; ".join(
                f"{source}: {totals[source]} citations ({scores[source]:.2f})"
                for source in sorted(totals)
            )
            + f" (log scale; scores 1 from {CITATION_REFERENCE:g})."
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
        The scored metric, ``FWCI / (1 + FWCI)`` (see
        :func:`ratio_to_average_scale`): 0.5 at the field average; or
        ``value=None`` without DOIs or FWCI values.
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
        value=ratio_to_average_scale(average),
        note=(
            f"Mean FWCI {average:.2f} over {len(values)} publication(s); "
            "1 is the field average and scores 0.5."
        ),
    )
