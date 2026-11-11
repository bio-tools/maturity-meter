"""Security metrics from resqui checks (Gitleaks, OpenSSF Scorecard)."""

from maturity_meter.components.utils.checks import (
    NO_RESQUI_NOTE,
    findings_note,
    resqui_verdict,
)
from maturity_meter.models import IngestedData, MetricResult


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
        return MetricResult(
            name="no_leaked_credentials", value=None, note=NO_RESQUI_NOTE
        )
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
            name="human_code_review_requirement", value=None, note=NO_RESQUI_NOTE
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
