"""Maintainability metrics.

Each function computes one metric from the ingested data and returns its
:class:`MetricResult`, scored with the placeholder helpers in
:mod:`maturity_meter.components.utils.scaling`. When several sources measure
the same thing, they are combined with :func:`placeholder_reconcile`.
"""

from pathlib import PurePosixPath

from maturity_meter.components.utils.checks import findings_note, resqui_verdict
from maturity_meter.components.utils.scaling import (
    placeholder_reconcile,
    placeholder_scale,
)
from maturity_meter.models import IngestedData, MetricResult

AVG_CCN_CAP = 10.0
DUPLICATE_RATE_CAP = 30.0

# Files that declare a project's dependencies, by ecosystem.
DEPENDENCY_MANIFESTS = {
    "requirements.txt",  # Python
    "pyproject.toml",
    "setup.py",
    "setup.cfg",
    "pipfile",
    "environment.yml",  # conda
    "environment.yaml",
    "package.json",  # JavaScript
    "description",  # R
    "renv.lock",
    "cargo.toml",  # Rust
    "go.mod",  # Go
    "pom.xml",  # Java
    "build.gradle",
    "build.gradle.kts",
    "gemfile",  # Ruby
    "cpanfile",  # Perl
    "project.toml",  # Julia
    "conanfile.txt",  # C/C++
    "vcpkg.json",
}

_NO_CODE_METRICS = "Code metrics unavailable (the repository could not be analysed)."
_NO_RESQUI = "resqui did not check this (it needs Docker and a GitHub repository)."


def avg_ccn(data: IngestedData) -> MetricResult:
    """Average cyclomatic complexity per function (lower is better).

    Parameters
    ----------
    data : IngestedData
        Ingested data; uses Lizard's ``avg_ccn`` from the code metrics.

    Returns
    -------
    MetricResult
        The scored metric (1 for 0, 0 from AVG_CCN_CAP), or ``value=None``
        without code metrics.
    """
    value = (data.code_metrics or {}).get("avg_ccn")
    if value is None:
        return MetricResult(name="avg_ccn", value=None, note=_NO_CODE_METRICS)
    return MetricResult(
        name="avg_ccn",
        value=placeholder_scale(value, cap=AVG_CCN_CAP, invert=True),
        note=(
            f"Average cyclomatic complexity {value:.2f} per function "
            f"(scores 0 from {AVG_CCN_CAP:g})."
        ),
    )


def duplicate_rate(data: IngestedData) -> MetricResult:
    """Share of duplicated code, in percent (lower is better).

    Parameters
    ----------
    data : IngestedData
        Ingested data; uses Lizard's ``duplicate_rate`` from the code metrics.

    Returns
    -------
    MetricResult
        The scored metric (1 for none, 0 from DUPLICATE_RATE_CAP percent), or
        ``value=None`` without code metrics.
    """
    value = (data.code_metrics or {}).get("duplicate_rate")
    if value is None:
        return MetricResult(name="duplicate_rate", value=None, note=_NO_CODE_METRICS)
    return MetricResult(
        name="duplicate_rate",
        value=placeholder_scale(value, cap=DUPLICATE_RATE_CAP, invert=True),
        note=f"{value:.1f}% duplicated code (scores 0 from {DUPLICATE_RATE_CAP:g}%).",
    )


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
        return MetricResult(name="has_ci-tests", value=None, note=_NO_RESQUI)
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


def has_releases(data: IngestedData) -> MetricResult:
    """Whether the software is published as versioned releases.

    Combines the latest GitHub/GitLab release and resqui's
    ``has_releases`` check (if run) with :func:`placeholder_reconcile`.

    Parameters
    ----------
    data : IngestedData
        Ingested data.

    Returns
    -------
    MetricResult
        1 if releases exist, 0 if not, or ``value=None`` if unknown.
    """
    repository_verdict = None
    if "latest_release" in data.repository:
        latest = data.repository.get("latest_release")
        repository_verdict = float(latest is not None)
    findings = {
        "repository releases": repository_verdict,
        "resqui check": resqui_verdict(data, "has_releases"),
    }
    value = placeholder_reconcile(list(findings.values()))
    if value is None:
        return MetricResult(
            name="has_releases", value=None, note="Release information unavailable."
        )
    note = findings_note(findings, "found", "none found")
    latest = data.repository.get("latest_release") or {}
    if latest.get("tag_name"):
        released = latest.get("published_at") or latest.get("released_at") or ""
        note += f" Latest: {latest['tag_name']} ({released[:10]})."
    return MetricResult(
        name="has_releases",
        value=value,
        note=note,
        suggestions=[]
        if value > 0
        else ["Publish versioned releases (e.g. tagged GitHub/GitLab releases)."],
    )


def requirements_specified(data: IngestedData) -> MetricResult:
    """Whether the software declares its dependencies.

    Combines a dependency manifest in the repository (e.g.
    ``requirements.txt``, ``pyproject.toml``, ``environment.yml``,
    ``package.json``, ``DESCRIPTION``, ``Cargo.toml``, ``go.mod``) and resqui's
    ``requirements_specified`` check (if run) with
    :func:`placeholder_reconcile`.

    Parameters
    ----------
    data : IngestedData
        Ingested data.

    Returns
    -------
    MetricResult
        1 if declared, 0 if not, or ``value=None`` without a file list or
        check.
    """
    files = data.repository.get("files")
    manifests = sorted(
        {
            PurePosixPath(str(f)).name
            for f in files or []
            if PurePosixPath(str(f).lower()).name in DEPENDENCY_MANIFESTS
        }
    )
    findings = {
        "dependency manifest": None if files is None else float(bool(manifests)),
        "resqui check": resqui_verdict(data, "requirements_specified"),
    }
    value = placeholder_reconcile(list(findings.values()))
    if value is None:
        return MetricResult(
            name="requirements_specified",
            value=None,
            note="Repository file list unavailable.",
        )
    note = findings_note(findings, "found", "not found")
    if manifests:
        note += f" Manifests: {', '.join(manifests)}."
    return MetricResult(
        name="requirements_specified",
        value=value,
        note=note,
        suggestions=[]
        if value > 0
        else ["Declare the dependencies (e.g. requirements.txt or environment.yml)."],
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
