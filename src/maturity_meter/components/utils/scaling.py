"""Shared helpers to turn raw metric values into scores and dimension scores.

All scores are in [0, 1]. Every helper here is a placeholder: deliberately
simple stand-ins until the real scaling, reconciliation and aggregation are
decided.
"""

from statistics import mean

from maturity_meter.components.utils.roles import role
from maturity_meter.models import MetricResult


@role("scaling")
def placeholder_scale(value: float, cap: float, invert: bool = False) -> float:
    """Placeholder scaling: linear from 0 (score 0) to ``cap`` (score 1).

    Parameters
    ----------
    value : float
        Raw value.
    cap : float
        Raw value that scores 1; anything above it also scores 1.
    invert : bool, default=False
        For metrics where lower is better: 0 scores 1 and ``cap`` scores 0.

    Returns
    -------
    float
        Score in [0, 1].
    """
    score = max(0.0, min(1.0, value / cap)) if cap > 0 else 0.0
    return 1.0 - score if invert else score


@role("reconciliation")
def placeholder_reconcile(values: list[float | None]) -> float | None:
    """Placeholder reconciliation of one quantity reported by several sources.

    Used when different sources measure the same thing (e.g. the citation
    count of one publication in OpenAlex and in Europe PMC).

    Parameters
    ----------
    values : list[float | None]
        The values from each source; None where a source has no value.

    Returns
    -------
    float | None
        The mean of the available values, or None if no source has one.
    """
    available = [v for v in values if v is not None]
    return mean(available) if available else None


@role("aggregation")
def placeholder_dimension_score(metrics: list[MetricResult]) -> float | None:
    """Placeholder dimension score: the mean of the assessed metrics.

    Parameters
    ----------
    metrics : list[MetricResult]
        Metric results of one dimension.

    Returns
    -------
    float | None
        Mean value of the metrics whose value is not None, or None if no
        metric was assessed.
    """
    values = [m.value for m in metrics if m.value is not None]
    return mean(values) if values else None
