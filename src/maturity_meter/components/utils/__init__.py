"""Shared helpers for the dimension components: scaling, reconciliation,
aspect combination and dimension aggregation, source reliability,
reading resqui and FAIR-Checker verdicts, and building metrics from them.
"""

from .checks import (
    Aspect,
    Pool,
    aspect_metric,
    has_any_file,
    reconcile,
    resqui_verdict,
    verdict_metric,
)
from .scaling import (
    aggregate_dimension,
    combine_aspects,
    reconcile_any,
    reconcile_evidence,
    reconcile_priority,
)

__all__ = [
    "Aspect",
    "aspect_metric",
    "Pool",
    "reconcile",
    "has_any_file",
    "combine_aspects",
    "aggregate_dimension",
    "reconcile_any",
    "reconcile_evidence",
    "reconcile_priority",
    "resqui_verdict",
    "verdict_metric",
]
