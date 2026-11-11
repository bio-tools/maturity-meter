"""Scientific impact metrics from the repository: stars and forks."""

from maturity_meter.components.utils.scaling import (
    placeholder_scale,
)
from maturity_meter.components.utils.sources import (
    repo_record,
)
from maturity_meter.models import IngestedData, MetricResult

STAR_CAP = 50.0


FORK_CAP = 25.0


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
    repo = repo_record(data) or {}
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
    forks = (repo_record(data) or {}).get("forks_count")
    if forks is None:
        return MetricResult(
            name="fork_count", value=None, note="Fork count unavailable."
        )
    return MetricResult(
        name="fork_count",
        value=placeholder_scale(forks, cap=FORK_CAP),
        note=f"{forks} forks (scores 1 from {FORK_CAP:g}).",
    )
