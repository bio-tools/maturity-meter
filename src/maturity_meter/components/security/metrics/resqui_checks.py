"""Security metrics from resqui checks (Gitleaks, OpenSSF Scorecard)."""

from maturity_meter.components.utils.checks import (
    NO_RESQUI_NOTE,
    resqui_verdict,
    verdict_metric,
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
    return verdict_metric(
        "no_leaked_credentials",
        {"Gitleaks": resqui_verdict(data, "no_leaked_credentials")},
        yes="no leaks found",
        no="leaks found",
        suggestion="Remove the leaked secrets from the history and rotate them.",
        missing=NO_RESQUI_NOTE,
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
    return verdict_metric(
        "human_code_review_requirement",
        {"OpenSSF Scorecard": resqui_verdict(data, "human_code_review_requirement")},
        yes="changes reviewed",
        no="changes not reviewed",
        suggestion="Require a review of pull/merge requests before merging.",
        missing=NO_RESQUI_NOTE,
    )
