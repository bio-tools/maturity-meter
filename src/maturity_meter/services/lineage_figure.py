"""Flow figure of a :class:`Lineage`: sources -> fields -> metrics -> dimensions.

The figure is a Mermaid flowchart with four columns:

1. ingested data sources (``repository``, ``openalex``, ...);
2. the fields read from each source;
3. the metrics that read them: each field's edge is labelled with the scaling
   applied to it, and the metric's reconciliation function (which combines
   its sources) is shown inside the metric's box;
4. the dimensions, with the aggregation function (which combines the metrics)
   as the edge label.

It is saved as Mermaid text (``.mmd``) or as an HTML page that renders it.
"""

import html
import re
from pathlib import Path

from maturity_meter.services.lineage import Lineage

UTILS_PACKAGE = "maturity_meter.components.utils"
MERMAID_SCRIPT = "https://cdn.jsdelivr.net/npm/mermaid@11.4.1/dist/mermaid.min.js"


def _split(path: str) -> tuple[str, str]:
    """Split a read path into its source and the field within it."""
    match = re.match(r"([^.\[]+)[.]?(.*)", path)
    source, field = (match.group(1), match.group(2)) if match else (path, "")
    return source, field or "(whole source)"


def _short(functions: list[str], package: str = UTILS_PACKAGE) -> str:
    """Short names of the functions in ``package``, joined for an edge label."""
    return ", ".join(f.rsplit(".", 1)[-1] for f in functions if f.startswith(package))


def _label(text: str) -> str:
    """Quote a node label for Mermaid."""
    # Entities keep Mermaid from reading quotes or ``*`` (as in ``[*]``) as
    # markup.
    return '"' + text.replace('"', "#quot;").replace("*", "#42;") + '"'


# Mermaid theme: light, rounded, smooth curves, quiet lines.
_INIT = (
    '%%{init: {"theme": "base", "themeVariables": {'
    '"fontFamily": "Helvetica Neue, Helvetica, Arial, sans-serif", '
    '"fontSize": "14px", "primaryTextColor": "#0f172a", "lineColor": "#cbd5e1", '
    '"clusterBkg": "#f8fafc", "clusterBorder": "#e2e8f0", '
    '"edgeLabelBackground": "#ffffff"}, '
    '"flowchart": {"curve": "basis", "nodeSpacing": 16, "rankSpacing": 80, '
    '"padding": 14}}}%%'
)

# Node shape (opening, closing) and style per column.
_SHAPES = {
    "sources": ("([", "])"),
    "fields": ("(", ")"),
    "metrics": ("[", "]"),
    "dimensions": ("{{", "}}"),
}
_CLASSES = {
    "sources": "fill:#dbeafe,stroke:#3b82f6,stroke-width:1.5px,color:#1e3a8a",
    "fields": "fill:#ffffff,stroke:#cbd5e1,stroke-width:1px,color:#334155",
    "metrics": "fill:#ecfdf5,stroke:#10b981,stroke-width:1.5px,color:#064e3b",
    "dimensions": (
        "fill:#fef3c7,stroke:#f59e0b,stroke-width:2px,color:#78350f,font-weight:bold"
    ),
}
_TITLES = {
    "sources": "Ingested sources",
    "fields": "Data fields",
    "metrics": "Metrics",
    "dimensions": "Dimensions",
}
# One colour per dimension, for its node and the edges flowing into it.
_PALETTE = ["#6366f1", "#10b981", "#f59e0b", "#ef4444", "#0ea5e9", "#a855f7"]
_SOURCE_EDGE = "#cbd5e1"


def _tint(color: str, amount: float = 0.15) -> str:
    """Mix a hex colour with white; ``amount`` is the share of the colour."""
    rgb = [int(color[i : i + 2], 16) for i in (1, 3, 5)]
    return "#" + "".join(f"{round(255 - (255 - c) * amount):02x}" for c in rgb)


def _dimension_title(dimension: str) -> str:
    return dimension.replace("_", " ").capitalize()


def dimension_colors(lineage: Lineage) -> dict[str, str]:
    """Colour of each dimension that has metrics, in figure order.

    Parameters
    ----------
    lineage : Lineage
        Traced lineage.

    Returns
    -------
    dict[str, str]
        Hex colour per dimension name.
    """
    shown = [name for name, dim in lineage.dimensions.items() if dim.metrics]
    return {name: _PALETTE[i % len(_PALETTE)] for i, name in enumerate(shown)}


def lineage_to_mermaid(lineage: Lineage) -> str:
    """Render the lineage as a styled Mermaid flowchart (left to right).

    Parameters
    ----------
    lineage : Lineage
        Traced lineage.

    Returns
    -------
    str
        Mermaid flowchart source, including its theme and styles.
    """
    ids: dict[tuple[str, str], str] = {}
    columns: dict[str, list[str]] = {column: [] for column in _SHAPES}
    edges: list[tuple[str, str, float]] = []  # (line, colour, width)
    colors = dimension_colors(lineage)

    def node(column: str, key: str, text: str) -> str:
        if (column, key) not in ids:
            node_id = f"{column[0]}{len(ids)}"
            ids[(column, key)] = node_id
            opening, closing = _SHAPES[column]
            columns[column].append(f"    {node_id}{opening}{_label(text)}{closing}")
        return ids[(column, key)]

    def edge(start: str, end: str, color: str, width: float, label: str = "") -> None:
        line = (
            f"  {start} -->|{_label(label)}| {end}" if label else f"  {start} --> {end}"
        )
        if all(line != existing for existing, _, _ in edges):
            edges.append((line, color, width))

    for dimension, color in colors.items():
        dim = lineage.dimensions[dimension]
        dimension_id = node("dimensions", dimension, _dimension_title(dimension))
        for metric_name, metric in dim.metrics.items():
            reconciliation = _short(metric.reconciliation)
            text = (
                f"{metric_name}<br/><i>{reconciliation}</i>"
                if reconciliation
                else metric_name
            )
            metric_id = node("metrics", f"{dimension}.{metric_name}", text)
            edge(metric_id, dimension_id, color, 2.5, _short(dim.aggregation))
            for path in metric.reads:
                source, field = _split(path)
                source_id = node("sources", source, source)
                field_id = node("fields", path, field)
                edge(source_id, field_id, _SOURCE_EDGE, 1.5)
                edge(field_id, metric_id, color, 1.5, _short(metric.scaling))

    lines = [_INIT, "flowchart LR"]
    for column, nodes in columns.items():
        lines += [f"  subgraph {column}[{_label(_TITLES[column])}]", *nodes, "  end"]
    lines += [line for line, _, _ in edges]
    for column, style in _CLASSES.items():
        lines.append(f"  classDef {column} {style}")
        node_ids = [node_id for (c, _), node_id in ids.items() if c == column]
        if node_ids:
            lines.append(f"  class {','.join(node_ids)} {column}")
        lines.append(f"  style {column} fill:#f8fafc,stroke:#e2e8f0,color:#64748b")
    for dimension, color in colors.items():
        lines.append(
            f"  style {ids[('dimensions', dimension)]} "
            f"fill:{_tint(color)},stroke:{color},stroke-width:2px,color:#0f172a"
        )
    for index, (_, color, width) in enumerate(edges):
        lines.append(f"  linkStyle {index} stroke:{color},stroke-width:{width}px")
    return "\n".join(lines) + "\n"


def lineage_to_html(lineage: Lineage) -> str:
    """Render the lineage as an HTML page that draws the Mermaid flowchart.

    Parameters
    ----------
    lineage : Lineage
        Traced lineage.

    Returns
    -------
    str
        A self-contained HTML page (Mermaid is loaded from a CDN).
    """
    swatches = "".join(
        f'<span class="key"><span class="swatch {column}"></span>{title}</span>'
        for column, title in _TITLES.items()
    )
    datasets = "".join(
        f"<li>{html.escape(dataset)}</li>" for dataset in lineage.datasets
    )
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Metric lineage</title>
<script src="{MERMAID_SCRIPT}"></script>
<style>
  :root {{ color-scheme: light; --ink: #0f172a; --muted: #64748b; --rule: #e2e8f0; }}
  body {{ margin: 0; background: #f1f5f9; color: var(--ink);
         font: 15px/1.5 Helvetica Neue, Helvetica, Arial, sans-serif; }}
  main {{ width: fit-content; max-width: 100%; margin: 0 auto;
          padding: 32px 16px 48px; box-sizing: border-box; }}
  .lede {{ max-width: 900px; }}
  h1 {{ font-size: 26px; margin: 0 0 4px; letter-spacing: -0.01em; }}
  .lede {{ color: var(--muted); margin: 0 0 20px; }}
  .legend {{ display: flex; flex-wrap: wrap; gap: 8px 20px; margin: 0 0 12px;
            font-size: 13px; color: #334155; }}
  .key {{ display: inline-flex; align-items: center; gap: 8px; }}
  .swatch {{ width: 16px; height: 12px; border-radius: 6px; border: 1.5px solid; }}
  .swatch.sources {{ background: #dbeafe; border-color: #3b82f6; }}
  .swatch.fields {{ background: #fff; border-color: #cbd5e1; border-radius: 4px; }}
  .swatch.metrics {{ background: #ecfdf5; border-color: #10b981; border-radius: 2px; }}
  .swatch.dimensions {{ background: #f1f5f9; border-color: #94a3b8; }}
  .card {{ background: #fff; border: 1px solid var(--rule); border-radius: 14px;
          padding: 20px; overflow-x: auto;
          box-shadow: 0 1px 2px rgba(15, 23, 42, .04),
                      0 8px 24px rgba(15, 23, 42, .06); }}
  /* Mermaid can measure a label a pixel or two narrower than it draws it;
     let the text overflow its box (shapes have padding) instead of clipping. */
  .mermaid {{ font: 14px/1.2 Helvetica Neue, Helvetica, Arial, sans-serif; }}
  .mermaid foreignObject {{ overflow: visible; }}
  footer {{ margin-top: 16px; font-size: 13px; color: var(--muted); }}
  footer ul {{ margin: 4px 0 0; padding-left: 18px; }}
</style>
</head>
<body>
<main>
  <h1>Metric lineage</h1>
  <p class="lede">Which ingested data each maturity metric reads, and the functions
  applied on the way: <b>scaling</b> on the edges from data fields,
  <b>reconciliation</b> (in italics) inside each metric, combining its sources,
  and <b>aggregation</b> on the edges into each dimension.</p>
  <div class="legend">{swatches}</div>
  <div class="card">
<div class="mermaid">
{html.escape(lineage_to_mermaid(lineage), quote=False)}</div>
  </div>
  <footer>Traced on:<ul>{datasets}</ul></footer>
</main>
<script>
mermaid.initialize({{ startOnLoad: true, flowchart: {{ useMaxWidth: false }} }});
</script>
</body>
</html>
"""


def save_figure(lineage: Lineage, path: Path) -> None:
    """Save the lineage figure: HTML for ``.html``, else Mermaid text.

    Parameters
    ----------
    lineage : Lineage
        Traced lineage.
    path : pathlib.Path
        File to write, e.g. ``lineage.html`` or ``lineage.mmd``.
    """
    is_html = path.suffix.lower() in (".html", ".htm")
    path.write_text(
        lineage_to_html(lineage) if is_html else lineage_to_mermaid(lineage)
    )
