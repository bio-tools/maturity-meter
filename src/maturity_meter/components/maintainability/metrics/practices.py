"""Maintainability metrics on development practices (CI tests, linting)."""

from maturity_meter.components.utils.checks import (
    NO_RESQUI_NOTE,
    findings_note,
    resqui_verdict,
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
    verdict = resqui_verdict(data, "has_ci-tests")
    if verdict is None:
        return MetricResult(name="has_ci-tests", value=None, note=NO_RESQUI_NOTE)
    return MetricResult(
        name="has_ci-tests",
        value=verdict,
        note=findings_note(
            {"OpenSSF Scorecard": verdict}, "changes tested in CI", "no CI tests"
        ),
        suggestions=[]
        if verdict
        else ["Run the tests in CI on every pull/merge request."],
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
    verdict = resqui_verdict(data, "has_no_linting_issues")
    if verdict is None:
        return MetricResult(
            name="has_no_linting_issues",
            value=None,
            note="Not checked: SuperLinter is not enabled in the resqui configuration.",
        )
    return MetricResult(
        name="has_no_linting_issues",
        value=verdict,
        note=findings_note({"SuperLinter": verdict}, "no issues", "issues found"),
        suggestions=[] if verdict else ["Fix the issues reported by the linters."],
    )
