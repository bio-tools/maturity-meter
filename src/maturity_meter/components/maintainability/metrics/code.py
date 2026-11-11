"""Maintainability metrics from the source code (Lizard)."""

from maturity_meter.components.utils.scaling import (
    placeholder_scale,
)
from maturity_meter.models import IngestedData, MetricResult

AVG_CCN_CAP = 10.0


DUPLICATE_RATE_CAP = 30.0


_NO_CODE_METRICS = "Code metrics unavailable (the repository could not be analysed)."


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
