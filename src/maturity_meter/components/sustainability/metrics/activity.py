"""Sustainability metrics on development activity."""

from datetime import UTC, datetime

from maturity_meter.components.utils.scaling import (
    placeholder_scale,
)
from maturity_meter.components.utils.sources import (
    parse_time,
    repo_record,
)
from maturity_meter.models import IngestedData, MetricResult

LAST_COMMIT_CAP_DAYS = 365.0


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
    repo = repo_record(data) or {}
    last = parse_time(repo.get("pushed_at") or repo.get("last_activity_at"))
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
