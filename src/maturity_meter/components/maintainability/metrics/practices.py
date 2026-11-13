"""Maintainability metrics on development practices (CI, linting)."""

from maturity_meter.components.utils.checks import (
    Aspect,
    aspect_metric,
    resqui_verdict,
)
from maturity_meter.components.utils.files import LINTER_FILES, is_ci_config
from maturity_meter.components.utils.sources import file_name, has_file
from maturity_meter.models import IngestedData, MetricResult


def continuous_integration(data: IngestedData) -> MetricResult:
    """Whether builds and tests run automatically on every change.

    Aspects and their sources:

    - CI configured: CI configuration files (GitHub Actions, GitLab CI,
      Travis, CircleCI, ...) and RSFC's ``repository_workflows`` check;
    - changes tested: OpenSSF Scorecard's ``has_ci-tests`` check, which looks
      for tests run on pull/merge requests before merging.

    Parameters
    ----------
    data : IngestedData
        Ingested data.

    Returns
    -------
    MetricResult
        The aspects combined, or ``value=None`` if no source could check.
    """
    return aspect_metric(
        "continuous_integration",
        {
            "CI configured": Aspect(
                {
                    "CI configuration": has_file(data, is_ci_config),
                    "RSFC repository workflows": resqui_verdict(
                        data, "repository_workflows"
                    ),
                },
                "Set up continuous integration (e.g. GitHub Actions).",
            ),
            "changes tested": Aspect(
                {"OpenSSF Scorecard": resqui_verdict(data, "has_ci-tests")},
                "Run the tests in CI on every pull/merge request.",
            ),
        },
    )


def linting(data: IngestedData) -> MetricResult:
    """Whether linters are used, and whether the code passes them.

    Aspects and their sources:

    - linting set up: linter and formatter configuration files (pre-commit,
      ruff, flake8, ESLint, clang-tidy, ...);
    - no linting issues: SuperLinter's ``has_no_linting_issues`` check, only
      available when SuperLinter is enabled in the resqui configuration.

    Parameters
    ----------
    data : IngestedData
        Ingested data.

    Returns
    -------
    MetricResult
        The aspects combined, or ``value=None`` if no source could check.
    """
    return aspect_metric(
        "linting",
        {
            "linting set up": Aspect(
                {
                    "linter configuration": has_file(
                        data,
                        lambda f: (
                            file_name(f) in LINTER_FILES
                            or file_name(f).startswith(".eslintrc")
                        ),
                    )
                },
                "Use linters or formatters (e.g. via pre-commit).",
            ),
            "no linting issues": Aspect(
                {"SuperLinter": resqui_verdict(data, "has_no_linting_issues")},
                "Fix the issues reported by the linters.",
            ),
        },
    )
