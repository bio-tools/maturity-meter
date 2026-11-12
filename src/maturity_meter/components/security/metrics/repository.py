"""Security metrics from the repository settings."""

from maturity_meter.components.utils.checks import verdict_metric
from maturity_meter.components.utils.sources import verdict
from maturity_meter.models import IngestedData, MetricResult


def default_branch_protected(data: IngestedData) -> MetricResult:
    """Whether the default branch is protected.

    Parameters
    ----------
    data : IngestedData
        Ingested data; uses the GitHub/GitLab ``default_branch_protected``.

    Returns
    -------
    MetricResult
        1 if protected, 0 if not, or ``value=None`` if unknown.
    """
    return verdict_metric(
        "default_branch_protected",
        {"default branch": verdict(data.repository.get("default_branch_protected"))},
        yes="protected",
        no="not protected",
        suggestion="Protect the default branch (e.g. require reviews or checks).",
        missing="Branch protection status unavailable.",
    )
