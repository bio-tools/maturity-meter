"""Maintainability metrics on releases and declared dependencies."""

from pathlib import PurePosixPath

from maturity_meter.components.utils.checks import (
    findings_note,
    resqui_verdict,
)
from maturity_meter.components.utils.files import (
    DEPENDENCY_MANIFESTS,
)
from maturity_meter.components.utils.scaling import (
    placeholder_reconcile,
)
from maturity_meter.models import IngestedData, MetricResult


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
