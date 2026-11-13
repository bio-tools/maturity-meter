"""Security metrics: change control, vulnerabilities, testing and hygiene."""

from maturity_meter.components.utils.checks import (
    NO_RESQUI_NOTE,
    Aspect,
    aspect_metric,
    resqui_verdict,
)
from maturity_meter.components.utils.sources import file_name, has_file, verdict
from maturity_meter.models import IngestedData, MetricResult


def change_control(data: IngestedData) -> MetricResult:
    """Whether changes to the code are controlled before they are merged.

    Aspects and their sources:

    - branch protection: whether the default branch is protected
      (GitHub/GitLab);
    - code review: OpenSSF Scorecard's ``human_code_review_requirement``
      check.

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
        "change_control",
        {
            "branch protection": Aspect(
                {
                    "default branch": verdict(
                        data.repository.get("default_branch_protected")
                    )
                },
                "Protect the default branch (e.g. require reviews or checks).",
            ),
            "code review": Aspect(
                {
                    "OpenSSF Scorecard": resqui_verdict(
                        data, "human_code_review_requirement"
                    )
                },
                "Require a review of pull/merge requests before merging.",
            ),
        },
    )


def vulnerability_management(data: IngestedData) -> MetricResult:
    """Whether known vulnerabilities are absent and can be reported.

    Aspects and their sources:

    - no critical vulnerabilities: OpenSSF Scorecard's
      ``no_critical_vulnerability`` check;
    - security policy: a ``SECURITY.md`` file anywhere in the repository.

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
        "vulnerability_management",
        {
            "no critical vulnerabilities": Aspect(
                {
                    "OpenSSF Scorecard": resqui_verdict(
                        data, "no_critical_vulnerability"
                    )
                },
                "Fix the known critical vulnerabilities (e.g. update dependencies).",
            ),
            "security policy": Aspect(
                {
                    "SECURITY.md": has_file(
                        data, lambda f: file_name(f) == "security.md"
                    )
                },
                "Add a SECURITY.md explaining how to report vulnerabilities.",
            ),
        },
    )


def security_testing(data: IngestedData) -> MetricResult:
    """Whether the code is checked for security defects.

    Aspects and their sources:

    - static analysis: OpenSSF Scorecard's
      ``static_analysis_common_vulnerabilities`` check (e.g. CodeQL);
    - fuzzing: OpenSSF Scorecard's ``uses_fuzzing`` check, mostly relevant to
      memory-unsafe languages.

    Parameters
    ----------
    data : IngestedData
        Ingested data.

    Returns
    -------
    MetricResult
        The aspects combined, or ``value=None`` if resqui did not check.
    """
    return aspect_metric(
        "security_testing",
        {
            "static analysis": Aspect(
                {
                    "OpenSSF Scorecard": resqui_verdict(
                        data, "static_analysis_common_vulnerabilities"
                    )
                },
                "Run security static analysis (e.g. CodeQL) in CI.",
            ),
            "fuzzing": Aspect(
                {"OpenSSF Scorecard": resqui_verdict(data, "uses_fuzzing")},
                "Fuzz the code that parses untrusted input.",
            ),
        },
        missing=NO_RESQUI_NOTE,
    )


def repository_hygiene(data: IngestedData) -> MetricResult:
    """Whether the repository is free of committed binaries and secrets.

    Aspects and their sources:

    - no binary artifacts: OpenSSF Scorecard's ``has_no_binary_artifacts``
      check;
    - ignore file: a ``.gitignore`` file anywhere in the repository;
    - no leaked credentials: Gitleaks' ``no_leaked_credentials`` check, only
      available when Gitleaks is enabled in the resqui configuration.

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
        "repository_hygiene",
        {
            "no binary artifacts": Aspect(
                {"OpenSSF Scorecard": resqui_verdict(data, "has_no_binary_artifacts")},
                "Remove compiled binaries from the repository.",
            ),
            "ignore file": Aspect(
                {".gitignore": has_file(data, lambda f: file_name(f) == ".gitignore")},
                "Add a .gitignore so build outputs and secrets are not committed.",
            ),
            "no leaked credentials": Aspect(
                {"Gitleaks": resqui_verdict(data, "no_leaked_credentials")},
                "Remove the leaked secrets from the history and rotate them.",
            ),
        },
    )
