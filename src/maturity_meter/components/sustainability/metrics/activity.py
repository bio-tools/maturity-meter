"""Sustainability metric on development activity."""

from datetime import UTC, datetime

from maturity_meter.components.utils.checks import (
    Aspect,
    aspect_metric,
    resqui_verdict,
)
from maturity_meter.components.utils.scaling import placeholder_scale
from maturity_meter.components.utils.sources import parse_time, repo_record
from maturity_meter.models import IngestedData, MetricResult

LAST_COMMIT_CAP_DAYS = 365.0


def _recency(data: IngestedData) -> tuple[float | None, str]:
    """Score of the last push (1 for today, 0 from the cap), and a label."""
    repo = repo_record(data) or {}
    last = parse_time(repo.get("pushed_at") or repo.get("last_activity_at"))
    if last is None:
        return None, "last activity"
    days = max(0.0, (datetime.now(UTC) - last).total_seconds() / 86400)
    return (
        placeholder_scale(days, cap=LAST_COMMIT_CAP_DAYS, invert=True),
        f"GitHub/GitLab ({days:.0f} days ago)",
    )


def development_activity(data: IngestedData) -> MetricResult:
    """Whether the software is still being developed.

    Aspects and their sources:

    - recent activity: days since the GitHub push or GitLab project activity
      (1 for today, 0 from LAST_COMMIT_CAP_DAYS; lower is better);
    - active project: OpenSSF Scorecard's ``project_is_active`` check (recent
      commits or issue activity).

    Mature, stable software may score low here without being abandoned.

    Parameters
    ----------
    data : IngestedData
        Ingested data.

    Returns
    -------
    MetricResult
        The aspects combined, or ``value=None`` if no source could check.
    """
    recency, label = _recency(data)
    return aspect_metric(
        "development_activity",
        {
            "recent activity": Aspect({label: recency}),
            "active project": Aspect(
                {"OpenSSF Scorecard": resqui_verdict(data, "project_is_active")}
            ),
        },
        missing="Last activity date unavailable.",
    )
