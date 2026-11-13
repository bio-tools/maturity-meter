"""Helpers to read yes/no verdicts and to build metrics from them.

A metric is either a single question answered by several sources
(:func:`verdict_metric`) or several distinct questions about one concept, its
aspects (:func:`aspect_metric`). Each question reconciles its sources with one
of three rules (see :data:`Rule`); aspects are combined with
:func:`combine_aspects`.
"""

from collections.abc import Collection, Iterable
from dataclasses import dataclass
from typing import Literal

from maturity_meter.components.utils.reliability import Evidence, assessment_tool
from maturity_meter.components.utils.scaling import (
    combine_aspects,
    reconcile_any,
    reconcile_evidence,
    reconcile_priority,
)
from maturity_meter.components.utils.sources import has_file
from maturity_meter.models import IngestedData, MetricResult

Rule = Literal["evidence", "any", "priority"]
"""How the sources of one question are reconciled.

- ``"evidence"``: the sources examine the same thing (e.g. the repository's
  licence file), so they are weighed by the reliability of their kind with
  :func:`reconcile_evidence`; every source must be :class:`Evidence`.
- ``"any"``: the sources look in different places or at alternatives (e.g.
  Bioconda or PyPI), so one of them suffices: :func:`reconcile_any`.
- ``"priority"``: the first available source, in the order given, e.g. a
  direct measurement before a second-hand figure: :func:`reconcile_priority`.
"""

# resqui does not serialize a pass/fail flag; the verdict is the plugin's
# ``output`` string. Other outputs (e.g. "error", "indeterminate") give no
# verdict.
PASSING_OUTPUTS = {"true", "valid", "secure"}
FAILING_OUTPUTS = {"false", "invalid", "insecure"}

# Note for metrics whose only source is a resqui check that did not run.
NO_RESQUI_NOTE = "resqui did not check this (it needs Docker and a GitHub repository)."


def resqui_verdict(
    data: IngestedData,
    indicator: str,
    plugins: Collection[str] | None = None,
) -> float | None:
    """Verdict of the resqui check(s) for one EVERSE indicator.

    Parameters
    ----------
    data : IngestedData
        Ingested data; uses ``quality_checks``.
    indicator : str
        EVERSE indicator identifier, e.g. ``"no_leaked_credentials"``.
    plugins : collection of str, optional
        Only use the checks of these plugins (``checkingSoftware`` names, e.g.
        ``{"RSFC", "OEBFAIR"}``); all plugins by default. Used to leave out a
        plugin whose verdict for the indicator is known to be unreliable.

    Returns
    -------
    float | None
        1.0 if passed, 0.0 if failed (the plugins' verdicts weighed as
        assessment-tool evidence when several check the indicator); None if
        resqui did not check it or gave no verdict.
    """
    verdicts: list[float | None] = []
    for check in (data.quality_checks or {}).get("checks") or []:
        assessed = str((check.get("assessesIndicator") or {}).get("@id", ""))
        if assessed.rstrip("/").rsplit("/", 1)[-1] != indicator:
            continue
        software = (check.get("checkingSoftware") or {}).get("name")
        if plugins is not None and software not in plugins:
            continue
        output = str(check.get("output", "")).lower()
        if output in PASSING_OUTPUTS:
            verdicts.append(1.0)
        elif output in FAILING_OUTPUTS:
            verdicts.append(0.0)
    return reconcile_evidence([assessment_tool(v) for v in verdicts])


def has_any_file(data: IngestedData, paths: Iterable[str]) -> float | None:
    """Whether the repository contains any of the given files.

    Parameters
    ----------
    data : IngestedData
        Ingested data; uses the repository ``files`` list.
    paths : iterable of str
        File paths relative to the repository root, compared
        case-insensitively (e.g. ``".github/dependabot.yml"``).

    Returns
    -------
    float | None
        1.0 if any is present, 0.0 if none is, or None without a (complete)
        file list (see :func:`~maturity_meter.components.utils.sources.has_file`).
    """
    wanted = {path.lower() for path in paths}
    return has_file(data, lambda f: f in wanted)


@dataclass(frozen=True)
class Pool:
    """Several sources examining the same thing, weighed as one finding.

    Used inside an ``"any"`` question for one place that several sources
    examine, e.g. the repository's licence file (the GitHub licence, the file
    itself, and the RSFC and OEBFAIR checks), next to other places.

    Parameters
    ----------
    evidence : dict[str, Evidence]
        Each source's answer and kind, reconciled with
        :func:`reconcile_evidence`.
    """

    evidence: dict[str, Evidence]

    @property
    def value(self) -> float | None:
        """The weighed answer of the pooled sources."""
        return reconcile_evidence(list(self.evidence.values()))


Finding = Evidence | Pool | float | None
"""One source's answer: with its kind of source (Evidence), a Pool of sources,
or a plain value (only for the ``"any"`` and ``"priority"`` rules)."""


def _value(finding: Finding) -> float | None:
    if isinstance(finding, Evidence | Pool):
        return finding.value
    return finding


def reconcile(findings: dict[str, Finding], rule: Rule) -> float | None:
    """Reconcile the sources of one question with ``rule`` (see :data:`Rule`).

    Parameters
    ----------
    findings : dict[str, Finding]
        Each source's answer, by source name.
    rule : {"evidence", "any", "priority"}
        How the answers are reconciled.

    Returns
    -------
    float | None
        The reconciled answer, or None if no source has one.

    Raises
    ------
    TypeError
        If the ``"evidence"`` rule gets a source without a kind of source.
    """
    if rule == "evidence":
        evidence = []
        for source, finding in findings.items():
            if not isinstance(finding, Evidence):
                raise TypeError(f"{source}: the evidence rule needs a source kind")
            evidence.append(finding)
        return reconcile_evidence(evidence)
    values = [_value(finding) for finding in findings.values()]
    return reconcile_any(values) if rule == "any" else reconcile_priority(values)


def _wording(value: float) -> str:
    if value == 1:
        return "yes"
    if value == 0:
        return "no"
    return f"{value:.2f}"


def _below_half(value: float | None) -> bool:
    return value is not None and value < 0.5


def _describe(findings: dict[str, Finding]) -> str:
    """Each source's answer, e.g. ``"LICENSE file yes, bio.tools no"``."""
    parts = []
    for source, finding in findings.items():
        value = _value(finding)
        if value is None:
            continue
        if isinstance(finding, Pool):
            inner = _describe(dict(finding.evidence))
            parts.append(f"{source} {_wording(value)} [{inner}]")
        else:
            parts.append(f"{source} {_wording(value)}")
    return ", ".join(parts)


def verdict_metric(
    name: str,
    findings: dict[str, Finding],
    *,
    rule: Rule,
    suggestion: str | None = None,
    missing: str = "No source could check this.",
    detail: str = "",
) -> MetricResult:
    """A metric answering one question from several sources.

    Parameters
    ----------
    name : str
        Metric name.
    findings : dict[str, Finding]
        Each source's answer, by source name.
    rule : {"evidence", "any", "priority"}
        How the answers are reconciled (see :data:`Rule`).
    suggestion : str, optional
        Suggestion given when the answer scores below 0.5.
    missing : str
        Note when no source has an answer.
    detail : str, optional
        Extra text appended to the note (e.g. which file was found).

    Returns
    -------
    MetricResult
        The reconciled metric, with a note giving each source's answer.
    """
    value = reconcile(findings, rule)
    if value is None:
        return MetricResult(name=name, value=None, note=missing)
    note = f"{_describe(findings)}. {detail}".strip()
    return MetricResult(
        name=name,
        value=value,
        note=note,
        suggestions=[suggestion] if suggestion and _below_half(value) else [],
    )


@dataclass(frozen=True)
class Aspect:
    """One question a metric answers, and every source's answer to it.

    Parameters
    ----------
    findings : dict[str, Finding]
        Each source's answer, by source name: a score in [0, 1] (1 or 0 for
        yes/no checks), or None when the source has no answer.
    suggestion : str, optional
        Suggestion given when the aspect scores below 0.5.
    rule : {"evidence", "any", "priority"}, default="any"
        How the answers are reconciled (see :data:`Rule`).
    """

    findings: dict[str, Finding]
    suggestion: str | None = None
    rule: Rule = "any"

    @property
    def value(self) -> float | None:
        """The reconciled answer, or None if no source has one."""
        return reconcile(self.findings, self.rule)


def aspect_metric(
    name: str,
    aspects: dict[str, Aspect],
    *,
    missing: str = "No source could check this.",
) -> MetricResult:
    """A metric made of several aspects (distinct questions) of one concept.

    Each aspect reconciles the sources that answer it; the metric's value
    combines the assessed aspects with :func:`combine_aspects`. An aspect
    no source could answer is left out rather than counted as a no.

    Parameters
    ----------
    name : str
        Metric name.
    aspects : dict[str, Aspect]
        The metric's aspects, by a short description (e.g. ``"declared"``).
    missing : str
        Note when no aspect could be assessed.

    Returns
    -------
    MetricResult
        The combined metric. Its note gives each aspect's answer and every
        source's answer to it; its suggestions those of the aspects scoring
        below 0.5.
    """
    values = {label: aspect.value for label, aspect in aspects.items()}
    value = combine_aspects(list(values.values()))
    if value is None:
        return MetricResult(name=name, value=None, note=missing)
    parts = []
    for label, aspect in aspects.items():
        answer = values[label]
        if answer is None:
            parts.append(f"{label}: unknown")
        else:
            parts.append(f"{label}: {_wording(answer)} ({_describe(aspect.findings)})")
    return MetricResult(
        name=name,
        value=value,
        note="; ".join(parts) + ".",
        suggestions=[
            aspect.suggestion
            for label, aspect in aspects.items()
            if aspect.suggestion and _below_half(values[label])
        ],
    )
