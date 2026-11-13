"""Overview: tables of the dimensions, metrics, sources, weights and functions.

Built from a traced :class:`~maturity_meter.services.lineage.Lineage` (so it
cannot drift from the code) and from the central definitions of importance
(:mod:`~maturity_meter.components.utils.importance`) and source reliability
(:mod:`~maturity_meter.components.utils.reliability`). Every metric, function
and definition links to where it is defined in the source code.
"""

import importlib
import inspect
import re
from collections import defaultdict
from importlib.metadata import PackageNotFoundError, metadata
from types import ModuleType
from typing import Any

from maturity_meter.components.utils import importance, reliability
from maturity_meter.services.lineage import Lineage, MetricLineage, SourceLineage

PACKAGE = "maturity_meter"
DEFAULT_REPOSITORY = "https://github.com/bio-tools/maturity-meter"
TIER_NAMES = {1: "supporting", 2: "important", 3: "essential"}
DIMENSION_TITLES = {
    "compatibility": "Compatibility",
    "fairness": "FAIRness",
    "maintainability": "Maintainability",
    "scientific_impact": "Scientific impact",
    "security": "Security",
    "sustainability": "Sustainability",
}
_ROLES = ("scaling", "reconciliation", "aggregation")


def repository_url() -> str:
    """The project's source code URL, from the package metadata."""
    try:
        urls = metadata(PACKAGE).get_all("Project-URL") or []
    except PackageNotFoundError:
        return DEFAULT_REPOSITORY
    for entry in urls:
        label, _, url = entry.partition(",")
        if label.strip().lower() in ("source code", "source", "repository"):
            return str(url).strip()
    return DEFAULT_REPOSITORY


class _Links:
    """Links to definitions in the source code at a given commit or branch."""

    def __init__(self, repository: str, ref: str):
        self.base = f"{repository.rstrip('/')}/blob/{ref}"

    def _url(self, module: ModuleType, line: int) -> str:
        path = module.__name__.replace(".", "/")
        # A package's code is in its __init__.py.
        file = (
            f"src/{path}/__init__.py"
            if hasattr(module, "__path__")
            else f"src/{path}.py"
        )
        return f"{self.base}/{file}#L{line}"

    def function(self, qualified: str, text: str | None = None) -> str:
        """A Markdown link to the function ``module.qualname``."""
        module_name, _, name = qualified.rpartition(".")
        try:
            module = importlib.import_module(module_name)
            obj = getattr(module, name)
            line = inspect.getsourcelines(obj)[1]
            module = importlib.import_module(obj.__module__)
        except (ImportError, AttributeError, OSError, TypeError):
            return f"`{text or name}`"
        return f"[`{text or name}`]({self._url(module, line)})"

    def constant(self, module: ModuleType, name: str) -> str:
        """A Markdown link to the module-level definition of ``name``."""
        source = inspect.getsource(module).splitlines()
        line = next(
            (
                number
                for number, text in enumerate(source, 1)
                if re.match(rf"{name}\s*[:=]", text)
            ),
            1,
        )
        return f"[`{name}`]({self._url(module, line)})"


def _cell(text: str) -> str:
    """Text safe inside a Markdown table cell."""
    return text.replace("|", "\\|").replace("\n", " ")


def _short(qualified: str) -> str:
    return qualified.rpartition(".")[2]


def _source(source: SourceLineage) -> str:
    """E.g. ``repository [GitHub/GitLab licence (repository), RSFC (...)]``."""
    if source.kind == "pool":
        inner = ", ".join(_source(s) for s in source.sources)
        return f"{source.name} [{inner}]"
    return f"{source.name} ({source.kind})" if source.kind else source.name


def _aspects(metric: MetricLineage) -> str:
    parts = []
    for aspect in metric.aspects:
        sources = ", ".join(_source(s) for s in aspect.sources)
        label = f"**{aspect.name}** " if aspect.name else ""
        parts.append(f"{label}*{aspect.rule}*: {sources}")
    return "<br>".join(parts) or "—"


def _table(header: list[str], rows: list[list[str]]) -> list[str]:
    return [
        "| " + " | ".join(header) + " |",
        "|" + "---|" * len(header),
        *("| " + " | ".join(_cell(c) for c in row) + " |" for row in rows),
        "",
    ]


def _source_name(path: str) -> str:
    return re.split(r"[.\[]", path, maxsplit=1)[0]


def overview_markdown(
    lineage: Lineage,
    *,
    repository: str | None = None,
    ref: str = "main",
) -> str:
    """Render the overview of the maturity model as a Markdown page.

    Parameters
    ----------
    lineage : Lineage
        Lineage traced on probe data that exercises every metric.
    repository : str, optional
        Source code URL the links point to; the project's by default.
    ref : str, default="main"
        Commit, tag or branch the links point to.

    Returns
    -------
    str
        The Markdown page.
    """
    links = _Links(repository or repository_url(), ref)
    lines = [
        "# Overview",
        "",
        "Every dimension, metric, source, weight and function of the maturity "
        "model, generated from the code (`maturity-meter overview`) on every "
        "documentation build. Names link to their definitions; see "
        "[Metrics](metrics.md) for the reasoning and "
        "[Metric lineage](lineage.md) for the figure.",
        "",
        "## Dimensions",
        "",
        f"Metric weights are defined in "
        f"{links.constant(importance, 'IMPORTANCE')}: "
        "3 essential, 2 important, 1 supporting.",
        "",
    ]
    rows = []
    for name, dim in lineage.dimensions.items():
        tiers: dict[int, list[str]] = defaultdict(list)
        for metric_name, metric in dim.metrics.items():
            tiers[int(metric.weight or 0)].append(metric_name)
        rows.append(
            [
                DIMENSION_TITLES.get(name, name),
                str(len(dim.metrics)),
                ", ".join(f"`{m}`" for m in tiers[3]) or "—",
                ", ".join(links.function(f) for f in dim.aggregation) or "—",
            ]
        )
    lines += _table(["Dimension", "Metrics", "Essential", "Aggregation"], rows)

    lines += ["## Metrics", ""]
    for name, dim in lineage.dimensions.items():
        lines += [f"### {DIMENSION_TITLES.get(name, name)}", ""]
        rows = []
        for metric_name, metric in sorted(
            dim.metrics.items(), key=lambda item: (-(item[1].weight or 0), item[0])
        ):
            weight = (
                f"{metric.weight:g} ({TIER_NAMES.get(int(metric.weight), '')})"
                if metric.weight is not None
                else "—"
            )
            rows.append(
                [
                    links.function(metric.function, metric_name),
                    weight,
                    metric.description,
                    _aspects(metric),
                    ", ".join(f"`{r}`" for r in metric.reads) or "—",
                    ", ".join(links.function(f) for f in metric.scaling) or "—",
                ]
            )
        lines += _table(
            [
                "Metric",
                "Weight",
                "Description",
                "Aspects (*rule*): sources (kind)",
                "Fields read",
                "Scaling",
            ],
            rows,
        )

    lines += [
        "## Kinds of sources",
        "",
        "Sources of an *evidence* question vote with the log-odds of their "
        f"kind's accuracy, defined in {links.constant(reliability, 'ACCURACY')}.",
        "",
    ]
    by_kind: dict[str, set[str]] = defaultdict(set)

    def collect(source: SourceLineage, prefix: str = "") -> None:
        if source.kind == "pool":
            for inner in source.sources:
                collect(inner, f"{prefix}{source.name}: ")
        elif source.kind:
            by_kind[source.kind].add(prefix + source.name)

    for dim in lineage.dimensions.values():
        for metric in dim.metrics.values():
            for aspect in metric.aspects:
                for source in aspect.sources:
                    collect(source)
    rows = [
        [
            kind.value,
            f"{accuracy:.2f}",
            f"{reliability.vote_weight(kind):.2f}",
            ", ".join(sorted(by_kind.get(kind.value, set()))) or "—",
        ]
        for kind, accuracy in reliability.ACCURACY.items()
    ]
    lines += _table(["Kind", "Accuracy", "Vote weight", "Sources"], rows)

    lines += ["## Ingested data", ""]
    fields: dict[str, set[str]] = defaultdict(set)
    users: dict[str, set[str]] = defaultdict(set)
    for dim_name, dim in lineage.dimensions.items():
        for metric_name, metric in dim.metrics.items():
            for path in metric.reads:
                data_source = _source_name(path)
                fields[data_source].add(path)
                users[data_source].add(f"{metric_name} ({DIMENSION_TITLES[dim_name]})")
    rows = [
        [
            f"`{name}`",
            ", ".join(f"`{p}`" for p in sorted(fields[name])),
            ", ".join(sorted(users[name])),
        ]
        for name in sorted(fields)
    ]
    lines += _table(["Source", "Fields read", "Metrics"], rows)

    lines += ["## Functions", ""]
    used: dict[str, dict[str, set[str]]] = {role: defaultdict(set) for role in _ROLES}
    for dim_name, dim in lineage.dimensions.items():
        for function in dim.aggregation:
            used["aggregation"][function].add(DIMENSION_TITLES[dim_name])
        for metric_name, metric in dim.metrics.items():
            for function in metric.scaling:
                used["scaling"][function].add(metric_name)
            for function in metric.reconciliation:
                used["reconciliation"][function].add(metric_name)
    rows = []
    for role in _ROLES:
        for function, names in sorted(used[role].items()):
            rows.append(
                [
                    links.function(function),
                    role,
                    _docstring_summary(function),
                    ", ".join(sorted(names)),
                ]
            )
    lines += _table(["Function", "Role", "Description", "Used by"], rows)
    return "\n".join(lines)


def _docstring_summary(qualified: str) -> str:
    module_name, _, name = qualified.rpartition(".")
    try:
        obj: Any = getattr(importlib.import_module(module_name), name)
    except (ImportError, AttributeError):
        return ""
    return (inspect.getdoc(obj) or "").split("\n")[0]
