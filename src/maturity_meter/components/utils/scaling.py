"""Shared helpers to turn raw metric values into scores and dimension scores.

All scores are in [0, 1]. The scaling functions map one source's raw value
onto [0, 1] before any reconciliation; each documents the reasoning and the
reference it is anchored on. Reconciliation combines several sources'
answers to one question, by one of three rules (evidence, any, priority).
Aspect combination and dimension aggregation are still placeholders until they
are decided.
"""

import math
from statistics import mean

from maturity_meter.components.utils.reliability import Evidence, vote_weight
from maturity_meter.components.utils.roles import role
from maturity_meter.models import MetricResult


def _clip(score: float) -> float:
    return max(0.0, min(1.0, score))


@role("scaling")
def log_scale(count: float, reference: float) -> float:
    """Score a heavily skewed count (stars, forks, citations) on a log scale.

    ``log(1 + count) / log(1 + reference)``, capped at 1. Such counts are
    roughly lognormal: a few tools have orders of magnitude more than the
    median, so a linear scale would put nearly every tool near 0 or 1. The
    ``log(1 + x)`` transform is the standard way to compare skewed citation
    counts (Thelwall, 2017, *J. Informetrics* 11:128), and the added 1 keeps 0
    at 0. Each doubling of the count raises the score by the same step.

    Parameters
    ----------
    count : float
        Raw count (0 or more).
    reference : float
        Count that scores 1, i.e. clearly established; above it also scores 1.

    Returns
    -------
    float
        Score in [0, 1].
    """
    return _clip(math.log1p(max(count, 0.0)) / math.log1p(reference))


@role("scaling")
def ratio_to_average_scale(ratio: float) -> float:
    """Score a ratio to an average (1 = average), e.g. FWCI, as ``r / (1 + r)``.

    The average scores 0.5, twice the average 0.67 and half of it 0.33, and the
    score approaches 1 without a cap, which suits the lognormal tail of such
    ratios. FWCI 1.0 is the world average of the field, publication year and
    document type.

    Parameters
    ----------
    ratio : float
        Ratio to the average (0 or more).

    Returns
    -------
    float
        Score in [0, 1).
    """
    ratio = max(ratio, 0.0)
    return ratio / (1.0 + ratio)


@role("scaling")
def recency_scale(days: float, grace_days: float, half_life_days: float) -> float:
    """Score the time since the last activity (lower is better).

    1 within ``grace_days``; after that the score halves every
    ``half_life_days``, so long inactivity approaches 0 without a cliff.

    Parameters
    ----------
    days : float
        Days since the last activity.
    grace_days : float
        Days of inactivity that still score 1.
    half_life_days : float
        Further days of inactivity that halve the score.

    Returns
    -------
    float
        Score in (0, 1].
    """
    if days <= grace_days:
        return 1.0
    return float(0.5 ** ((days - grace_days) / half_life_days))


@role("scaling")
def half_point_decay_scale(value: float, half_point: float) -> float:
    """Score a duration where lower is better, as ``1 / (1 + value / half)``.

    0 scores 1 and ``half_point`` scores 0.5; the score keeps falling for
    longer durations without reaching 0, which suits skewed durations with no
    natural maximum (e.g. issue close times).

    Parameters
    ----------
    value : float
        Raw duration (0 or more).
    half_point : float
        Duration that scores 0.5.

    Returns
    -------
    float
        Score in (0, 1].
    """
    return 1.0 / (1.0 + max(value, 0.0) / half_point)


@role("scaling")
def effective_number_scale(effective_number: float) -> float:
    """Score an effective number (e.g. inverse Simpson index) as ``1 - 1/D``.

    ``1 - 1/D`` is the Gini-Simpson index: the probability that two randomly
    picked units (e.g. commits) belong to different categories (e.g.
    contributors). One contributor scores 0, two equal contributors 0.5, four
    0.75, approaching 1 as the work is spread over more people.

    Parameters
    ----------
    effective_number : float
        Effective number, 1 or more.

    Returns
    -------
    float
        Score in [0, 1).
    """
    return _clip(1.0 - 1.0 / max(effective_number, 1.0))


@role("scaling")
def linear_band_scale(value: float, best: float, worst: float) -> float:
    """Score linearly between a best and a worst value (in either order).

    ``best`` or better scores 1, ``worst`` or worse scores 0. Used where an
    established threshold marks the end of the range, e.g. a cyclomatic
    complexity of 10 per function (McCabe; NIST SP 500-235).

    Parameters
    ----------
    value : float
        Raw value.
    best : float
        Value (and anything better) that scores 1.
    worst : float
        Value (and anything worse) that scores 0.

    Returns
    -------
    float
        Score in [0, 1].
    """
    return _clip((value - worst) / (best - worst))


@role("reconciliation")
def reconcile_evidence(evidence: list[Evidence]) -> float | None:
    """Probability that a yes/no answer is yes, from several sources' evidence.

    Accuracy-weighted voting: every source with an answer votes with the weight
    of its kind (``ln(A / (1 - A))``, see
    :mod:`~maturity_meter.components.utils.reliability`), for yes or against;
    a graded answer (e.g. 0.5) votes in proportion (``2 * value - 1``). The
    summed votes are the log-odds of yes, starting from even odds. One
    repository observation outweighs several weak heuristics; agreeing sources
    strengthen each other; equally trusted sources that disagree give 0.5.
    A single answer is returned as it is, since accuracy only weighs sources
    against each other.

    Used when the sources examine the same thing (e.g. whether a licence is
    declared), so a "no" from a trusted source is real evidence against.

    Parameters
    ----------
    evidence : list[Evidence]
        Each source's answer and kind; answers of None are left out.

    Returns
    -------
    float | None
        Probability in [0, 1], or None if no source has an answer.
    """
    answered = [(e.kind, e.value) for e in evidence if e.value is not None]
    if not answered:
        return None
    if len(answered) == 1:
        # Nothing to weigh it against: the answer is used as it is.
        return answered[0][1]
    votes = sum(vote_weight(kind) * (2.0 * value - 1.0) for kind, value in answered)
    return 1.0 / (1.0 + math.exp(-votes))


@role("reconciliation")
def reconcile_any(values: list[float | None]) -> float | None:
    """The best answer of several sources: any one of them suffices.

    Used when the sources look in different places or at alternatives (e.g.
    Bioconda, Debian or PyPI for "published package"; a CITATION file or a
    README section for "how to cite"), so one source's "no" says nothing
    about the others, and for citation counts, which databases undercount by
    different amounts (e.g. Martin-Martin et al. 2018).

    Parameters
    ----------
    values : list[float | None]
        Each source's answer or score; None where a source has none.

    Returns
    -------
    float | None
        The highest available value, or None if no source has one.
    """
    available = [v for v in values if v is not None]
    return max(available) if available else None


@role("reconciliation")
def reconcile_priority(values: list[float | None]) -> float | None:
    """The first available answer, in order of preference.

    Used when one source measures directly and another reports a second-hand
    figure of unknown method (e.g. issue close times computed from the
    repository's issues, then OpenEBench's figure).

    Parameters
    ----------
    values : list[float | None]
        Answers from the most to the least preferred source.

    Returns
    -------
    float | None
        The first value that is not None, or None.
    """
    return next((v for v in values if v is not None), None)


@role("reconciliation")
def placeholder_combine(values: list[float | None]) -> float | None:
    """Placeholder combination of a metric's aspects into the metric's value.

    Used when a metric covers several distinct questions (aspects) about one
    concept, e.g. licensing: is a licence declared, is it open source, is it
    machine-readable. Unlike the reconciliation functions, the values are
    answers to different questions, not one question from several sources.

    Parameters
    ----------
    values : list[float | None]
        The value of each aspect; None where an aspect could not be assessed.

    Returns
    -------
    float | None
        The mean of the assessed aspects, or None if none was assessed.
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
