"""Security metrics.

Each function computes one metric from the ingested data and returns its
:class:`MetricResult`. Verdicts are 1 (pass) or 0 (fail); when several sources
check the same thing, they are combined with :func:`placeholder_reconcile`.
``dependency_management`` is shared with the compatibility dimension.
"""

from maturity_meter.components.shared.metrics import dependency_management
from maturity_meter.components.utils.checks import findings_note, resqui_verdict
from maturity_meter.models import IngestedData, MetricResult

__all__ = [
    "default_branch_protected",
    "dependency_management",
    "human_code_review_requirement",
    "no_leaked_credentials",
]

_NO_RESQUI = "resqui did not check this (it needs Docker and a GitHub repository)."


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


def no_leaked_credentials(data: IngestedData) -> MetricResult:
    """Whether no secrets were found in the repository history.

    Parameters
    ----------
    data : IngestedData
        Ingested data; uses resqui's Gitleaks check.

    Returns
    -------
    MetricResult
        1 if no leaks were found, 0 if some were, or ``value=None`` if
        resqui did not check.
    """
    verdict = resqui_verdict(data, "no_leaked_credentials")
    if verdict is None:
        return MetricResult(name="no_leaked_credentials", value=None, note=_NO_RESQUI)
    return MetricResult(
        name="no_leaked_credentials",
        value=verdict,
        note=findings_note({"Gitleaks": verdict}, "no leaks found", "leaks found"),
        suggestions=[]
        if verdict
        else ["Remove the leaked secrets from the history and rotate them."],
    )


def human_code_review_requirement(data: IngestedData) -> MetricResult:
    """Whether changes are reviewed by a person before they are merged.

    Parameters
    ----------
    data : IngestedData
        Ingested data; uses resqui's OpenSSF Scorecard check.

    Returns
    -------
    MetricResult
        1 if changes are reviewed, 0 if not, or ``value=None`` if resqui did
        not check.
    """
    verdict = resqui_verdict(data, "human_code_review_requirement")
    if verdict is None:
        return MetricResult(
            name="human_code_review_requirement", value=None, note=_NO_RESQUI
        )
    return MetricResult(
        name="human_code_review_requirement",
        value=verdict,
        note=findings_note(
            {"OpenSSF Scorecard": verdict}, "changes reviewed", "changes not reviewed"
        ),
        suggestions=[]
        if verdict
        else ["Require a review of pull/merge requests before merging."],
    )
