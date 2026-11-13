"""Shared helpers for the dimension components: placeholder scaling,
reconciliation, aspect combination and dimension scores, reading resqui and
FAIR-Checker verdicts, and building metrics from them.
"""

from .checks import (
    Aspect,
    aspect_metric,
    findings_note,
    has_any_file,
    resqui_verdict,
    verdict_metric,
)
from .scaling import (
    placeholder_combine,
    placeholder_dimension_score,
    placeholder_reconcile,
    placeholder_scale,
)

__all__ = [
    "Aspect",
    "aspect_metric",
    "findings_note",
    "has_any_file",
    "placeholder_combine",
    "placeholder_dimension_score",
    "placeholder_reconcile",
    "placeholder_scale",
    "resqui_verdict",
    "verdict_metric",
]
