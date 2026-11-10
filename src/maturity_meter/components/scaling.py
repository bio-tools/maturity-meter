"""Shared helpers to turn raw metric values into scores and dimension scores.

All scores are in [0, 1]. :func:`scale` is a placeholder for now.
"""

from statistics import mean

from maturity_meter.models import MetricResult


def scale(value: float, cap: float) -> float:
    """Placeholder scaling: linear from 0 (score 0) to ``cap`` (score 1).

    A deliberately simple stand-in used by every metric until the real
    scoring is decided.

    Parameters
    ----------
    value : float
        Raw value.
    cap : float
        Raw value that scores 1; anything above it also scores 1.

    Returns
    -------
    float
        Score in [0, 1].
    """
    return max(0.0, min(1.0, value / cap)) if cap > 0 else 0.0


def mean_score(metrics: list[MetricResult]) -> float | None:
    """Mean of the assessed metrics' values, or None if none was assessed.

    Parameters
    ----------
    metrics : list[MetricResult]
        Metric results of one dimension.

    Returns
    -------
    float | None
        Mean value of the metrics whose value is not None.
    """
    values = [m.value for m in metrics if m.value is not None]
    return mean(values) if values else None
