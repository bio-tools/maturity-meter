"""Maintainability metrics from the source code (Lizard)."""

from maturity_meter.components.utils.scaling import linear_band_scale
from maturity_meter.models import IngestedData, MetricResult

# Cyclomatic complexity: 1 is the minimum (no branches); 10 is McCabe's and
# NIST's (SP 500-235) recommended maximum per function, above which it should
# be split. An average at that maximum means typical functions are at the
# limit, so it scores 0.
AVG_CCN_BEST = 1.0
AVG_CCN_WORST = 10.0

# Duplicated code, in percent. SonarQube's recommended quality gate ("Sonar
# way") allows at most 3% duplicated lines, so up to 3% scores 1; the score
# falls linearly to 0 for fully duplicated code (100%). Lizard detects
# duplicates by tokens, so some repetition (tests, generated code) is expected.
DUPLICATE_RATE_BEST = 3.0
DUPLICATE_RATE_WORST = 100.0

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
        The scored metric (1 at AVG_CCN_BEST, 0 from AVG_CCN_WORST, linear in
        between), or ``value=None`` without code metrics.
    """
    value = (data.code_metrics or {}).get("avg_ccn")
    if value is None:
        return MetricResult(name="avg_ccn", value=None, note=_NO_CODE_METRICS)
    return MetricResult(
        name="avg_ccn",
        value=linear_band_scale(value, best=AVG_CCN_BEST, worst=AVG_CCN_WORST),
        note=(
            f"Average cyclomatic complexity {value:.2f} per function "
            f"(scores 1 at {AVG_CCN_BEST:g}, 0 from {AVG_CCN_WORST:g})."
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
        The scored metric (1 up to DUPLICATE_RATE_BEST percent, 0 from
        DUPLICATE_RATE_WORST, linear in between), or ``value=None`` without
        code metrics.
    """
    value = (data.code_metrics or {}).get("duplicate_rate")
    if value is None:
        return MetricResult(name="duplicate_rate", value=None, note=_NO_CODE_METRICS)
    return MetricResult(
        name="duplicate_rate",
        value=linear_band_scale(
            value, best=DUPLICATE_RATE_BEST, worst=DUPLICATE_RATE_WORST
        ),
        note=(
            f"{value:.1f}% duplicated code (scores 1 up to "
            f"{DUPLICATE_RATE_BEST:g}%, 0 from {DUPLICATE_RATE_WORST:g}%)."
        ),
    )
