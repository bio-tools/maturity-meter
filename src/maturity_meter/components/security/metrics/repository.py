"""Security metrics from the repository settings."""

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
    protected = data.repository.get("default_branch_protected")
    if protected is None:
        return MetricResult(
            name="default_branch_protected",
            value=None,
            note="Branch protection status unavailable.",
        )
    return MetricResult(
        name="default_branch_protected",
        value=float(protected),
        note="Default branch is protected."
        if protected
        else "Default branch is not protected.",
        suggestions=[]
        if protected
        else ["Protect the default branch (e.g. require reviews or passing checks)."],
    )
