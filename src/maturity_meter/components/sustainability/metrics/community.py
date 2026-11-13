"""Sustainability metrics on the contributor community."""

from maturity_meter.components.utils.scaling import (
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
