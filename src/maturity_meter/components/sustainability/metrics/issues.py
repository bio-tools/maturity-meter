"""Sustainability metrics on issue handling."""

import re
from statistics import median
from typing import Any

from maturity_meter.components.utils.scaling import (
    half_point_decay_scale,
    reconcile_priority,
)
from maturity_meter.components.utils.sources import (
    parse_time,
)
from maturity_meter.models import IngestedData, MetricResult

# Close time that scores 0.5 (see half_point_decay_scale): a month, close to
# the median of bio.tools-registered GitHub repositories (about 46 days).
# CHAOSS gives no benchmark for a good close time.
CLOSE_TIME_HALF_DAYS = 30.0

_ISO_DURATION = re.compile(
    r"^P(?:(?P<days>\d+(?:\.\d+)?)D)?(?:T(?:(?P<hours>\d+(?:\.\d+)?)H)?"
    r"(?:(?P<minutes>\d+(?:\.\d+)?)M)?(?:(?P<seconds>\d+(?:\.\d+)?)S)?)?$"
)


def _iso_duration_days(value: Any) -> float | None:
    """Days in an ISO 8601 duration such as ``P3DT4H``, or None."""
    match = _ISO_DURATION.match(value) if isinstance(value, str) else None
    if not match or not any(match.groupdict().values()):
        return None
    parts = {k: float(v) for k, v in match.groupdict().items() if v}
    return (
        parts.get("days", 0.0)
        + parts.get("hours", 0.0) / 24
        + parts.get("minutes", 0.0) / 1440
        + parts.get("seconds", 0.0) / 86400
    )


def _close_days(data: IngestedData) -> list[float]:
    """Days from opening to closing of each recently closed issue."""
    durations = []
    for issue in data.repository.get("closed_issues") or []:
        created = parse_time(issue.get("created_at"))
        closed = parse_time(issue.get("closed_at"))
        if created and closed:
            durations.append((closed - created).total_seconds() / 86400)
    return durations


def resolved_issue_share(data: IngestedData) -> MetricResult:
    """Share of the reported issues that have been resolved (closed).

    ``closed / (open + closed)``, already in [0, 1]. The number of open issues
    alone grows with a tool's use rather than with neglect; relative to all
    reported issues it shows whether the backlog is kept under control.

    Parameters
    ----------
    data : IngestedData
        Ingested data; uses the open-issue count and the recently closed
        issues (pull requests excluded). On busy repositories the closed
        issues are a capped sample of the most recent ones, so the share is
        then a lower bound.

    Returns
    -------
    MetricResult
        The share, or ``value=None`` without issue data or without any issues.
    """
    open_count = data.repository.get("open_issues")
    closed = data.repository.get("closed_issues")
    if open_count is None or closed is None:
        return MetricResult(
            name="resolved_issue_share",
            value=None,
            note="Issue counts unavailable.",
        )
    total = open_count + len(closed)
    if total == 0:
        return MetricResult(
            name="resolved_issue_share", value=None, note="No issues reported."
        )
    share = len(closed) / total
    return MetricResult(
        name="resolved_issue_share",
        value=share,
        note=f"{len(closed)} of {total} reported issues closed; {open_count} open.",
        suggestions=["Triage and close the open issues."] if share < 0.5 else [],
    )


def issue_close_time(data: IngestedData) -> MetricResult:
    """How quickly issues are closed (lower is better).

    Each source is scaled with :func:`half_point_decay_scale` (0.5 at
    CLOSE_TIME_HALF_DAYS); the repository's own issues are used when
    available, and OpenEBench's figure (of unknown sample and method) only
    otherwise (:func:`reconcile_priority`):

    - the median close time of the recently closed GitHub/GitLab issues (the
      median, as CHAOSS recommends, since a few long-open issues skew the
      mean);
    - OpenEBench's ``support.issue_tracking.resolve_time`` (an ISO 8601
      duration).

    Parameters
    ----------
    data : IngestedData
        Ingested data.

    Returns
    -------
    MetricResult
        The reconciled score, or ``value=None`` without closed issues or a
        resolve time.
    """
    durations = _close_days(data)
    repo_days = median(durations) if durations else None
    metrics = (data.openebench or {}).get("metrics") or {}
    tracking = (metrics.get("support") or {}).get("issue_tracking") or {}
    openebench_days = _iso_duration_days(tracking.get("resolve_time"))
    found = {
        f"median of {len(durations)} closed issues": repo_days,
        "OpenEBench": openebench_days,
    }
    scores = {
        source: half_point_decay_scale(days, half_point=CLOSE_TIME_HALF_DAYS)
        for source, days in found.items()
        if days is not None
    }
    if not scores:
        return MetricResult(
            name="issue_close_time",
            value=None,
            note="No closed issues or resolve time found.",
        )
    return MetricResult(
        name="issue_close_time",
        value=reconcile_priority(list(scores.values())),
        note=(
            "; ".join(
                f"{source}: {found[source]:.1f} days ({score:.2f})"
                for source, score in scores.items()
            )
            + f" (scores 0.5 at {CLOSE_TIME_HALF_DAYS:g} days)."
        ),
    )
