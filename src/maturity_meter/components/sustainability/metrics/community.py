"""Sustainability metrics on the contributor community."""

from pathlib import PurePosixPath

from maturity_meter.components.utils.checks import (
    resqui_verdict,
)
from maturity_meter.components.utils.scaling import (
    placeholder_reconcile,
    placeholder_scale,
)
from maturity_meter.models import IngestedData, MetricResult

SIMPSON_CAP = 4.0


def _is_bot(name: str) -> bool:
    """Whether a contributor name looks like a bot account."""
    lowered = name.lower()
    return lowered.endswith("[bot]") or lowered.endswith(" bot") or lowered == "bot"


def inverse_simpson_index(data: IngestedData) -> MetricResult:
    """Contributor diversity: inverse Simpson index of commit shares.

    1 means one person made all commits; N means N people contributed
    equally. Bot accounts are left out.

    Parameters
    ----------
    data : IngestedData
        Ingested data; uses the GitHub/GitLab ``contributors`` commit counts.

    Returns
    -------
    MetricResult
        The scored metric (scaled up to SIMPSON_CAP), or ``value=None``
        without contributors.
    """
    contributors = data.repository.get("contributors") or []
    humans = [
        c
        for c in contributors
        if c.get("contributions") and not _is_bot(str(c.get("name") or ""))
    ]
    total = sum(c["contributions"] for c in humans)
    if not total:
        return MetricResult(
            name="inverse_simpson_index", value=None, note="No contributors found."
        )
    index = 1 / sum((c["contributions"] / total) ** 2 for c in humans)
    bots = len(contributors) - len(humans)
    return MetricResult(
        name="inverse_simpson_index",
        value=placeholder_scale(index, cap=SIMPSON_CAP),
        note=(
            f"Index {index:.2f} over {len(humans)} contributor(s)"
            + (f", {bots} bot(s) excluded" if bots else "")
            + f" (scores 1 from {SIMPSON_CAP:g})."
        ),
    )


def has_contribution_guidelines(data: IngestedData) -> MetricResult:
    """Whether the project provides contribution guidelines.

    Combines a ``CONTRIBUTING*`` file in the repository and resqui's
    ``has_contribution_guidelines`` check (if run) with
    :func:`placeholder_reconcile`.

    Parameters
    ----------
    data : IngestedData
        Ingested data.

    Returns
    -------
    MetricResult
        1 if found, 0 if not, or ``value=None`` without a file list or check.
    """
    files = data.repository.get("files")
    file_verdict = (
        None
        if files is None
        else float(
            any(PurePosixPath(f).name.lower().startswith("contributing") for f in files)
        )
    )
    resqui = resqui_verdict(data, "has_contribution_guidelines")
    value = placeholder_reconcile([file_verdict, resqui])
    if value is None:
        return MetricResult(
            name="has_contribution_guidelines",
            value=None,
            note="Repository file list unavailable.",
        )
    # Name each source's finding, so a disagreement (e.g. 0.5) is explained.
    findings = {"CONTRIBUTING file": file_verdict, "resqui check": resqui}
    note = "; ".join(
        f"{source}: {'found' if verdict else 'not found'}"
        for source, verdict in findings.items()
        if verdict is not None
    )
    return MetricResult(
        name="has_contribution_guidelines",
        value=value,
        note=f"{note}.",
        suggestions=[]
        if file_verdict
        else ["Add a CONTRIBUTING.md describing how to contribute."],
    )
