"""Scientific impact metrics from the repository: stars and forks."""

from maturity_meter.components.utils.scaling import log_scale
from maturity_meter.components.utils.sources import (
    repo_record,
)
from maturity_meter.models import IngestedData, MetricResult

# Counts that score 1 on the log scale (see log_scale): about the top 5% of
# bio.tools-registered GitHub repositories (median: 6 stars, 2 forks).
STAR_REFERENCE = 100.0
FORK_REFERENCE = 25.0


def star_count(data: IngestedData) -> MetricResult:
    """Repository stars, on a log scale up to STAR_REFERENCE.

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
        value=log_scale(stars, reference=STAR_REFERENCE),
        note=f"{stars} stars (log scale; scores 1 from {STAR_REFERENCE:g}).",
    )


def fork_count(data: IngestedData) -> MetricResult:
    """Repository forks, on a log scale up to FORK_REFERENCE.

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
        value=log_scale(forks, reference=FORK_REFERENCE),
        note=f"{forks} forks (log scale; scores 1 from {FORK_REFERENCE:g}).",
    )
