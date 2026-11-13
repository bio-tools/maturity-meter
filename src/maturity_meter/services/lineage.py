"""Lineage: which ingested data and helper functions each metric uses.

The lineage is traced, not declared, so it cannot drift from the code. Every
dimension's metric functions are discovered automatically and run on
already-ingested data wrapped in recording proxies, which log each field read.
A profiler hook logs every function from :mod:`maturity_meter.components`
that runs, grouped by the role its helper declares: scaling (applied to data
fields), reconciliation (combining sources into a metric) and aggregation
(combining metrics into a dimension).

Any field of :class:`IngestedData` is recorded, including sources added
later, whether a metric reads keys (``d[k]``, ``d.get(k)``, ``k in d``),
iterates (``for k in d``, ``d.keys()``, ``d.items()``, ``d.values()``), takes
``len(d)`` or a truth value, or just uses the field as a whole.

Tracing sees only the code paths the data triggers, so tracing several
datasets (from different tools) and merging them gives a fuller picture.
"""

import dataclasses
import importlib
import importlib.util
import inspect
import sys
from collections.abc import Callable, Iterable
from functools import partial
from pathlib import Path
from types import FrameType, ModuleType
from typing import Any, cast

from pydantic import BaseModel, Field

from maturity_meter.components.utils.checks import record_aspects
from maturity_meter.components.utils.importance import IMPORTANCE
from maturity_meter.components.utils.roles import ROLE_ATTRIBUTE
from maturity_meter.models import Evaluation, IngestedData, MetricResult

COMPONENTS_PACKAGE = "maturity_meter.components"


class SourceLineage(BaseModel):
    """One source answering an aspect of a metric.

    Parameters
    ----------
    name : str
        Source name, as in the metric's note (e.g. ``"LICENSE file"``).
    kind : str | None
        Kind of source, which sets its reliability (e.g. ``"repository"``), or
        ``"pool"`` for several sources weighed together; None if untyped.
    sources : list[SourceLineage]
        The pooled sources, for a pool.
    """

    name: str
    kind: str | None = None
    sources: list["SourceLineage"] = Field(default_factory=list)


class AspectLineage(BaseModel):
    """One question a metric answers, and how its sources are reconciled.

    Parameters
    ----------
    name : str
        Aspect name; empty for a metric that answers a single question.
    rule : str
        Reconciliation rule: ``"evidence"``, ``"any"`` or ``"priority"``.
    sources : list[SourceLineage]
        The sources answering it.
    """

    name: str
    rule: str
    sources: list[SourceLineage] = Field(default_factory=list)


class MetricLineage(BaseModel):
    """What one metric uses.

    Parameters
    ----------
    function : str
        Qualified name of the metric function.
    description : str
        First line of the metric function's docstring.
    weight : float | None
        Importance of the metric in this dimension's score (1 supporting, 2
        important, 3 essential), or None if unweighted.
    aspects : list[AspectLineage]
        Questions the metric answers and their sources, for metrics built from
        yes/no checks; empty for numeric metrics.
    reads : list[str]
        Ingested fields the metric read, e.g. ``"openalex[*].fwci"``; ``[*]``
        stands for any DOI, IRI or list item.
    scaling : list[str]
        Scaling functions it applied, which turn field values into scores.
    reconciliation : list[str]
        Reconciliation functions it applied, which combine values from
        several sources into the metric's value.
    helpers : list[str]
        Other component functions it called (e.g. parsing or lookups).
    """

    function: str
    description: str = ""
    weight: float | None = None
    aspects: list[AspectLineage] = Field(default_factory=list)
    reads: list[str] = Field(default_factory=list)
    scaling: list[str] = Field(default_factory=list)
    reconciliation: list[str] = Field(default_factory=list)
    helpers: list[str] = Field(default_factory=list)


class DimensionLineage(BaseModel):
    """What one dimension uses.

    Parameters
    ----------
    aggregation : list[str]
        Functions that combine the metrics into the dimension's score.
    helpers : list[str]
        Other component functions the dimension calls itself.
    metrics : dict[str, MetricLineage]
        Lineage per metric, keyed by metric name.
    """

    aggregation: list[str] = Field(default_factory=list)
    helpers: list[str] = Field(default_factory=list)
    metrics: dict[str, MetricLineage] = Field(default_factory=dict)


class Lineage(BaseModel):
    """Lineage of every dimension.

    Parameters
    ----------
    datasets : list[str]
        Repositories of the datasets the lineage was traced on.
    dimensions : dict[str, DimensionLineage]
        Lineage per dimension.
    """

    datasets: list[str] = Field(default_factory=list)
    dimensions: dict[str, DimensionLineage] = Field(default_factory=dict)

    def to_json(self) -> str:
        """Serialize the lineage as indented JSON.

        Returns
        -------
        str
            The lineage as JSON.
        """
        return self.model_dump_json(indent=2)

    def save(self, path: Path) -> None:
        """Write the lineage to ``path`` as indented JSON.

        Parameters
        ----------
        path : pathlib.Path
            File to write; it is overwritten if it exists.
        """
        path.write_text(self.to_json() + "\n")


# --- recording proxies ------------------------------------------------------


def _wrap(value: Any, path: str, log: set[str]) -> Any:
    """Wrap a value so that reads from it are logged under ``path``.

    Dicts, lists, pydantic models and dataclass instances are wrapped (their
    contents recursively); other values (numbers, strings, ...) are returned
    as they are, their read having been logged by whoever returned them.
    """
    if isinstance(value, dict):
        return _RecordingDict(value, path, log)
    if isinstance(value, list):
        return [_wrap(item, f"{path}[*]", log) for item in value]
    if isinstance(value, BaseModel) or (
        dataclasses.is_dataclass(value) and not isinstance(value, type)
    ):
        return _RecordingObject(value, path, log)
    return value


class _RecordingDict(dict[str, Any]):
    """A dict that logs every read from it.

    Reading a key (``d[k]``, ``d.get(k)``) or testing for one (``k in d``)
    logs ``path.k`` (or ``path[*]`` for identifier keys such as DOIs).
    Iterating its keys, items or values logs ``path[*]``, so per-DOI,
    per-IRI and per-item keys collapse to one entry. Taking its length or
    truth value logs ``path`` itself.
    """

    def __init__(self, data: dict[str, Any], path: str, log: set[str]):
        super().__init__(data)
        self._path = path
        self._log = log

    def _key_path(self, key: object) -> str:
        """Path of ``key``; identifier-like keys collapse to ``[*]``.

        Keys containing ``/`` or ``:`` (DOIs, IRIs, URLs) identify one item of
        a per-item mapping, so ``edam.get(iri)`` is recorded like iterating
        ``edam``, not as one path per IRI.
        """
        text = str(key)
        if "/" in text or ":" in text:
            return f"{self._path}[*]"
        return f"{self._path}.{text}"

    def _read(self, key: str) -> Any:
        path = self._key_path(key)
        self._log.add(path)
        return _wrap(super().__getitem__(key), path, self._log)

    def __getitem__(self, key: str) -> Any:
        return self._read(key)

    def get(self, key: str, default: Any = None) -> Any:
        if super().__contains__(key):
            return self._read(key)
        self._log.add(self._key_path(key))
        return default

    def __contains__(self, key: object) -> bool:
        self._log.add(self._key_path(key))
        return super().__contains__(key)

    def __iter__(self) -> Any:
        self._log.add(f"{self._path}[*]")
        return super().__iter__()

    def keys(self) -> Any:
        self._log.add(f"{self._path}[*]")
        return super().keys()

    def __len__(self) -> int:
        self._log.add(self._path)
        return super().__len__()

    def __bool__(self) -> bool:
        self._log.add(self._path)
        return super().__len__() > 0

    def items(self) -> Any:
        path = f"{self._path}[*]"
        self._log.add(path)
        return [(k, _wrap(v, path, self._log)) for k, v in super().items()]

    def values(self) -> Any:
        return [value for _, value in self.items()]


class _RecordingObject:
    """Proxy for an object that logs each attribute read.

    Used for :class:`IngestedData` itself (fields are top-level paths, e.g.
    ``repository``) and for nested models and dataclasses (e.g.
    ``request.dois``). Methods are passed through without being logged.
    """

    def __init__(self, target: Any, path: str, log: set[str]):
        self._target = target
        self._path = path
        self._log = log

    def __getattr__(self, name: str) -> Any:
        value = getattr(self._target, name)
        if callable(value) and not isinstance(value, dict | list):
            return value
        path = f"{self._path}.{name}" if self._path else name
        self._log.add(path)
        return _wrap(value, path, self._log)


def _recording(data: IngestedData, log: set[str]) -> IngestedData:
    """A view of ``data`` that logs every read into ``log``."""
    recording: Any = _RecordingObject(data, "", log)
    return cast(IngestedData, recording)


def _leaves(paths: Iterable[str]) -> list[str]:
    """Drop paths that are only a prefix of a more specific logged path."""
    paths = set(paths)
    return sorted(
        p
        for p in paths
        if not any(
            o != p and (o.startswith(p + ".") or o.startswith(p + "[")) for o in paths
        )
    )


# --- function tracing -------------------------------------------------------


def _called_functions(
    run: Callable[[], Any], exclude: set[str]
) -> tuple[Any, dict[str, str]]:
    """Run ``run``; return its result and the component functions it called.

    The functions are mapped to their role (see
    :func:`maturity_meter.components.utils.roles.role`), or ``"helper"``.
    """
    called: dict[str, str] = {}

    def profile(frame: FrameType, event: str, arg: Any) -> None:
        if event != "call":
            return
        module = frame.f_globals.get("__name__", "")
        qualname = frame.f_code.co_qualname
        # Skip comprehensions, lambdas and nested helpers.
        if module.startswith(COMPONENTS_PACKAGE) and "<" not in qualname:
            name = f"{module}.{qualname}"
            if name not in exclude:
                function = frame.f_globals.get(frame.f_code.co_name)
                called[name] = getattr(function, ROLE_ATTRIBUTE, "helper")

    previous = sys.getprofile()
    sys.setprofile(profile)
    try:
        result = run()
    finally:
        sys.setprofile(previous)
    return result, called


# --- discovery --------------------------------------------------------------


def _optional_module(name: str) -> ModuleType | None:
    """Import ``name`` if it exists, else return None."""
    return importlib.import_module(name) if importlib.util.find_spec(name) else None


def _metric_functions(dimension: str) -> list[Callable[[IngestedData], Any]]:
    """The metric functions in a dimension's ``metrics`` module.

    A metric is any public function there that takes only the ingested data
    and returns a :class:`MetricResult`, including shared metrics imported
    from elsewhere. Helpers (other return types or extra parameters, such as
    ``verdict_metric``) are left out.
    """
    module = _optional_module(f"{COMPONENTS_PACKAGE}.{dimension}.metrics")
    if module is None:
        return []
    return [
        fn
        for name, fn in inspect.getmembers(module, inspect.isfunction)
        if not name.startswith("_") and _is_metric(fn)
    ]


def _is_metric(fn: Callable[..., Any]) -> bool:
    """Whether ``fn`` looks like ``metric(data: IngestedData) -> MetricResult``."""
    signature = inspect.signature(fn)
    return (
        signature.return_annotation in (MetricResult, "MetricResult")
        and len(signature.parameters) == 1
    )


def _merge(existing: list[str], called: dict[str, str], kind: str) -> list[str]:
    """``existing`` plus the called functions of the given role, sorted."""
    return sorted({*existing, *(name for name, role in called.items() if role == kind)})


def _qualified(fn: Callable[..., Any]) -> str:
    return f"{fn.__module__}.{fn.__qualname__}"


# --- tracing ----------------------------------------------------------------


def trace_lineage(datasets: Iterable[IngestedData]) -> Lineage:
    """Trace which data and functions every metric and dimension uses.

    Parameters
    ----------
    datasets : iterable of IngestedData
        Already-ingested data to run the metrics on; results are merged.

    Returns
    -------
    Lineage
        The merged lineage of every dimension and metric.
    """
    datasets = list(datasets)
    lineage = Lineage(datasets=[d.request.repository for d in datasets])
    for dimension in Evaluation.model_fields:
        evaluate = importlib.import_module(
            f"{COMPONENTS_PACKAGE}.{dimension}.eval"
        ).eval
        metric_functions = _metric_functions(dimension)
        metric_names = {_qualified(fn) for fn in metric_functions}
        dim = DimensionLineage()
        dim_functions: dict[str, str] = {}
        inside_metrics: set[str] = set()
        for data in datasets:
            # The dimension's own functions: those called outside its metrics.
            _, called = _called_functions(
                partial(evaluate, data), exclude={_qualified(evaluate)}
            )
            dim_functions |= called
            for fn in metric_functions:
                log: set[str] = set()
                with record_aspects() as aspects:
                    result, called = _called_functions(
                        partial(fn, _recording(data, log)), exclude={_qualified(fn)}
                    )
                inside_metrics |= set(called)
                weight = IMPORTANCE.get(dimension, {}).get(result.name)
                metric = dim.metrics.setdefault(
                    result.name,
                    MetricLineage(
                        function=_qualified(fn),
                        description=(inspect.getdoc(fn) or "").split("\n")[0],
                        weight=None if weight is None else float(weight),
                    ),
                )
                if aspects and not metric.aspects:
                    metric.aspects = [AspectLineage(**a) for a in aspects]
                metric.reads = _leaves({*metric.reads, *log})
                metric.scaling = _merge(metric.scaling, called, "scaling")
                metric.reconciliation = _merge(
                    metric.reconciliation, called, "reconciliation"
                )
                metric.helpers = _merge(metric.helpers, called, "helper")
        own = {
            name: kind
            for name, kind in dim_functions.items()
            if name not in metric_names and name not in inside_metrics
        }
        dim.aggregation = _merge([], own, "aggregation")
        dim.helpers = sorted(
            name for name, kind in own.items() if kind != "aggregation"
        )
        lineage.dimensions[dimension] = dim
    return lineage
