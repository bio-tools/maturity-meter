"""Sustainability metrics on issue handling."""

import re
from statistics import mean
from typing import Any

from maturity_meter.components.utils.scaling import (
    placeholder_reconcile,
    placeholder_scale,
)
from maturity_meter.components.utils.sources import (
    parse_time,
)
from maturity_meter.models import IngestedData, MetricResult

OPEN_ISSUES_CAP = 20.0


CLOSE_TIME_CAP_DAYS = 250.0


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


def num_open_issues(data: IngestedData) -> MetricResult:
    """Number of open issues, excluding pull requests (lower is better).

    Parameters
    ----------
    data : IngestedData
        Ingested data; uses the GitHub/GitLab ``open_issues`` count.

    Returns
    -------
    MetricResult
        The scored metric (1 for none, 0 from OPEN_ISSUES_CAP), or
        ``value=None`` if the count is unavailable.
    """
    count = data.repository.get("open_issues")
    if count is None:
        return MetricResult(
            name="num_open_issues", value=None, note="Open issue count unavailable."
        )
    return MetricResult(
        name="num_open_issues",
        value=placeholder_scale(count, cap=OPEN_ISSUES_CAP, invert=True),
        note=f"{count} open issues (scores 0 from {OPEN_ISSUES_CAP:g}).",
    )


def avg_issue_close_time_days(data: IngestedData) -> MetricResult:
    """Average time to close an issue, in days (lower is better).

    Combines the mean close time of the recently closed GitHub/GitLab issues
    and OpenEBench's ``support.issue_tracking.resolve_time`` (when given as an
    ISO 8601 duration) with :func:`placeholder_reconcile`.

    Parameters
    ----------
    data : IngestedData
        Ingested data.

    Returns
    -------
    MetricResult
        The scored metric (1 for instant, 0 from CLOSE_TIME_CAP_DAYS), or
        ``value=None`` without closed issues or a resolve time.
    """
    durations = []
    for issue in data.repository.get("closed_issues") or []:
        created = parse_time(issue.get("created_at"))
        closed = parse_time(issue.get("closed_at"))
        if created and closed:
            durations.append((closed - created).total_seconds() / 86400)
    repo_days = mean(durations) if durations else None
    metrics = (data.openebench or {}).get("metrics") or {}
    tracking = (metrics.get("support") or {}).get("issue_tracking") or {}
    openebench_days = _iso_duration_days(tracking.get("resolve_time"))

    days = placeholder_reconcile([repo_days, openebench_days])
    if days is None:
        return MetricResult(
            name="avg_issue_close_time_days",
            value=None,
            note="No closed issues or resolve time found.",
        )
    sources = []
    if repo_days is not None:
        sources.append(f"{len(durations)} closed issues: {repo_days:.1f} days")
    if openebench_days is not None:
        sources.append(f"OpenEBench: {openebench_days:.1f} days")
    return MetricResult(
        name="avg_issue_close_time_days",
        value=placeholder_scale(days, cap=CLOSE_TIME_CAP_DAYS, invert=True),
        note=(
            f"{days:.1f} days on average ({'; '.join(sources)}; "
            f"scores 0 from {CLOSE_TIME_CAP_DAYS:g})."
        ),
    )
