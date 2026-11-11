"""Security metrics.

Each function computes one metric from the ingested data and returns its
:class:`MetricResult`. Verdicts are 1 (pass) or 0 (fail); when several sources
check the same thing, they are combined with :func:`placeholder_reconcile`.
"""

from maturity_meter.components.utils.checks import has_any_file, resqui_verdict
from maturity_meter.components.utils.scaling import placeholder_reconcile
from maturity_meter.models import IngestedData, MetricResult

# Configuration files of dependency update tools (Dependabot, Renovate).
DEPENDENCY_UPDATE_FILES = (
    ".github/dependabot.yml",
    ".github/dependabot.yaml",
    "renovate.json",
    "renovate.json5",
    ".renovaterc",
    ".renovaterc.json",
    ".github/renovate.json",
    ".github/renovate.json5",
    ".gitlab/renovate.json",
)

_NO_RESQUI = "resqui did not check this (it needs Docker and a GitHub repository)."


def _findings(findings: dict[str, float | None], yes: str, no: str) -> str:
    """Name each source's verdict, so a disagreement (e.g. 0.5) is explained."""
    return (
        "; ".join(
            f"{source}: {yes if verdict else no}"
            for source, verdict in findings.items()
            if verdict is not None
        )
        + "."
    )


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
        note=_findings({"Gitleaks": verdict}, "no leaks found", "leaks found"),
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
        note=_findings(
            {"OpenSSF Scorecard": verdict}, "changes reviewed", "changes not reviewed"
        ),
        suggestions=[]
        if verdict
        else ["Require a review of pull/merge requests before merging."],
    )


def dependency_management(data: IngestedData) -> MetricResult:
    """Whether dependencies are kept up to date by a tool.

    Combines resqui's OpenSSF Scorecard check and a Dependabot or Renovate
    configuration file in the repository with :func:`placeholder_reconcile`.

    Parameters
    ----------
    data : IngestedData
        Ingested data.

    Returns
    -------
    MetricResult
        1 if a dependency update tool is used, 0 if not, or ``value=None``
        without a check or file list.
    """
    findings = {
        "OpenSSF Scorecard": resqui_verdict(data, "dependency_management"),
        "Dependabot/Renovate config": has_any_file(data, DEPENDENCY_UPDATE_FILES),
    }
    value = placeholder_reconcile(list(findings.values()))
    if value is None:
        return MetricResult(
            name="dependency_management",
            value=None,
            note="No dependency check or file list available.",
        )
    return MetricResult(
        name="dependency_management",
        value=value,
        note=_findings(findings, "found", "not found"),
        # Only suggest one when no source found a tool.
        suggestions=[]
        if value > 0
        else ["Configure a dependency update tool such as Dependabot or Renovate."],
    )
