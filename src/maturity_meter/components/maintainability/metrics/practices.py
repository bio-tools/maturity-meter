"""Maintainability metrics on development practices (CI tests, linting)."""

from maturity_meter.components.utils.checks import (
    NO_RESQUI_NOTE,
    resqui_verdict,
    verdict_metric,
)
from maturity_meter.models import IngestedData, MetricResult


def has_ci_tests(data: IngestedData) -> MetricResult:
    """Whether changes are tested in continuous integration before merging.

    Parameters
    ----------
    data : IngestedData
        Ingested data; uses resqui's OpenSSF Scorecard check.

    Returns
    -------
    MetricResult
        1 if tested, 0 if not, or ``value=None`` if resqui did not check.
    """
    return verdict_metric(
        "has_ci-tests",
        {"OpenSSF Scorecard": resqui_verdict(data, "has_ci-tests")},
        yes="changes tested in CI",
        no="no CI tests",
        suggestion="Run the tests in CI on every pull/merge request.",
        missing=NO_RESQUI_NOTE,
    )


def has_no_linting_issues(data: IngestedData) -> MetricResult:
    """Whether linting reports no issues.

    Parameters
    ----------
    data : IngestedData
        Ingested data; uses resqui's SuperLinter check, which is only
        available when SuperLinter is enabled in the resqui configuration.

    Returns
    -------
    MetricResult
        1 if no issues, 0 if there are some, or ``value=None`` if not checked.
    """
    return verdict_metric(
        "has_no_linting_issues",
        {"SuperLinter": resqui_verdict(data, "has_no_linting_issues")},
        yes="no issues",
        no="issues found",
        suggestion="Fix the issues reported by the linters.",
        missing="Not checked: SuperLinter is not enabled in the resqui configuration.",
    )
