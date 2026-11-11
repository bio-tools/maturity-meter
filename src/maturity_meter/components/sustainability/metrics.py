"""Sustainability metrics.

Each function computes one metric from the ingested data and returns its
:class:`MetricResult`, scored with the placeholder helpers in
:mod:`maturity_meter.components.utils.scaling`. When several sources measure the
same thing, all of them are combined with :func:`placeholder_reconcile`.
"""

import re
from datetime import UTC, datetime
from pathlib import PurePosixPath
from statistics import mean
from typing import Any

from maturity_meter.components.utils.checks import resqui_verdict
from maturity_meter.components.utils.scaling import (
    placeholder_reconcile,
    placeholder_scale,
)
from maturity_meter.models import IngestedData, MetricResult

LAST_COMMIT_CAP_DAYS = 365.0
OPEN_ISSUES_CAP = 20.0
CLOSE_TIME_CAP_DAYS = 250.0
SIMPSON_CAP = 4.0

_ISO_DURATION = re.compile(
    r"^P(?:(?P<days>\d+(?:\.\d+)?)D)?(?:T(?:(?P<hours>\d+(?:\.\d+)?)H)?"
    r"(?:(?P<minutes>\d+(?:\.\d+)?)M)?(?:(?P<seconds>\d+(?:\.\d+)?)S)?)?$"
)


def _repo(data: IngestedData) -> dict[str, Any]:
    """The repository record (GitHub or GitLab)."""
    record: dict[str, Any] = data.repository.get("repo") or {}
    return record


def _parse_time(value: Any) -> datetime | None:
    """Parse an ISO 8601 timestamp (GitHub and GitLab style), or None."""
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)


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


def _is_bot(name: str) -> bool:
    """Whether a contributor name looks like a bot account."""
    lowered = name.lower()
    return lowered.endswith("[bot]") or lowered.endswith(" bot") or lowered == "bot"


def days_since_last_commit(data: IngestedData) -> MetricResult:
    """Days since the repository was last pushed to (lower is better).

    Parameters
    ----------
    data : IngestedData
        Ingested data; uses GitHub ``pushed_at`` or GitLab
        ``last_activity_at`` of the repository record.

    Returns
    -------
    MetricResult
        The scored metric (1 for today, 0 from LAST_COMMIT_CAP_DAYS), or
        ``value=None`` without a timestamp.
    """
    repo = _repo(data)
    last = _parse_time(repo.get("pushed_at") or repo.get("last_activity_at"))
    if last is None:
        return MetricResult(
            name="days_since_last_commit",
            value=None,
            note="Last activity date unavailable.",
        )
    days = max(0.0, (datetime.now(UTC) - last).total_seconds() / 86400)
    return MetricResult(
        name="days_since_last_commit",
        value=placeholder_scale(days, cap=LAST_COMMIT_CAP_DAYS, invert=True),
        note=(
            f"Last activity {days:.0f} days ago "
            f"(scores 0 from {LAST_COMMIT_CAP_DAYS:g})."
        ),
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
        created = _parse_time(issue.get("created_at"))
        closed = _parse_time(issue.get("closed_at"))
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


def inverse_simpson_index(data: IngestedData) -> MetricResult:
    """Contributor diversity: inverse Simpson index of commit shares.

    1 means one person made all commits; N means N people contributed
    equally. Bot accounts are left out.

    Parameters
    ----------
    data : IngestedData
        Ingested data; uses the GitHub/GitLab ``contributors`` commit counts.

    Returns
    -------
    MetricResult
        The scored metric (scaled up to SIMPSON_CAP), or ``value=None``
        without contributors.
    """
    contributors = data.repository.get("contributors") or []
    humans = [
        c
        for c in contributors
        if c.get("contributions") and not _is_bot(str(c.get("name") or ""))
    ]
    total = sum(c["contributions"] for c in humans)
    if not total:
        return MetricResult(
            name="inverse_simpson_index", value=None, note="No contributors found."
        )
    index = 1 / sum((c["contributions"] / total) ** 2 for c in humans)
    bots = len(contributors) - len(humans)
    return MetricResult(
        name="inverse_simpson_index",
        value=placeholder_scale(index, cap=SIMPSON_CAP),
        note=(
            f"Index {index:.2f} over {len(humans)} contributor(s)"
            + (f", {bots} bot(s) excluded" if bots else "")
            + f" (scores 1 from {SIMPSON_CAP:g})."
        ),
    )


def has_contribution_guidelines(data: IngestedData) -> MetricResult:
    """Whether the project provides contribution guidelines.

    Combines a ``CONTRIBUTING*`` file in the repository and resqui's
    ``has_contribution_guidelines`` check (if run) with
    :func:`placeholder_reconcile`.

    Parameters
    ----------
    data : IngestedData
        Ingested data.

    Returns
    -------
    MetricResult
        1 if found, 0 if not, or ``value=None`` without a file list or check.
    """
    files = data.repository.get("files")
    file_verdict = (
        None
        if files is None
        else float(
            any(PurePosixPath(f).name.lower().startswith("contributing") for f in files)
        )
    )
    resqui = resqui_verdict(data, "has_contribution_guidelines")
    value = placeholder_reconcile([file_verdict, resqui])
    if value is None:
        return MetricResult(
            name="has_contribution_guidelines",
            value=None,
            note="Repository file list unavailable.",
        )
    # Name each source's finding, so a disagreement (e.g. 0.5) is explained.
    findings = {"CONTRIBUTING file": file_verdict, "resqui check": resqui}
    note = "; ".join(
        f"{source}: {'found' if verdict else 'not found'}"
        for source, verdict in findings.items()
        if verdict is not None
    )
    return MetricResult(
        name="has_contribution_guidelines",
        value=value,
        note=f"{note}.",
        suggestions=[]
        if file_verdict
        else ["Add a CONTRIBUTING.md describing how to contribute."],
    )
