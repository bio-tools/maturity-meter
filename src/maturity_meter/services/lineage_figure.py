"""Flow figure of a :class:`Lineage`: sources -> fields -> metrics -> dimensions.

The figure is a Mermaid flowchart with four columns:

1. ingested data sources (``repository``, ``openalex``, ...);
2. the fields read from each source;
3. the metrics that read them: each field's edge is labelled with the scaling
   applied to it, and the metric's reconciliation function (which combines
   its sources) is shown inside the metric's box;
4. the dimensions, with their aggregation function (which combines the
   metrics into the dimension's score) shown inside the dimension's box.

It is saved as Mermaid text (``.mmd``) or as an HTML page that renders it. In
the HTML page, clicking a node shows only what it is connected to (everything
upstream and downstream of it).
"""

import html
import re
from pathlib import Path

from maturity_meter.services.lineage import Lineage

UTILS_PACKAGE = "maturity_meter.components.utils"
MERMAID_SCRIPT = "https://cdn.jsdelivr.net/npm/mermaid@11.4.1/dist/mermaid.min.js"


_TIER_NAMES = {1: "supporting", 2: "important", 3: "essential"}


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
        # The aggregation belongs to the dimension, so it is shown in its box.
        aggregation = _short(dim.aggregation)
        title = _dimension_title(dimension)
        dimension_id = node(
            "dimensions",
            dimension,
            f"{title}<br/><i>{aggregation}</i>" if aggregation else title,
        )
        for metric_name, metric in dim.metrics.items():
            reconciliation = _short(metric.reconciliation)
            title = metric_name
            if metric.weight is not None:
                title += f" (×{metric.weight:g} {_TIER_NAMES[int(metric.weight)]})"
            text = f"{title}<br/><i>{reconciliation}</i>" if reconciliation else title
            metric_id = node("metrics", f"{dimension}.{metric_name}", text)
            # The edge to the dimension is as thick as the metric's weight.
            edge(metric_id, dimension_id, color, 1.0 + (metric.weight or 1.5))
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


# Clicking a node fades everything that is not upstream or downstream of it.
# Mermaid names nodes ``flowchart-<id>-<n>`` and edges ``L_<from>_<to>_<n>``,
# with one edge label per edge in definition order (node ids have no ``_``).
_FOCUS_SCRIPT = """
mermaid.initialize({ startOnLoad: false, flowchart: { useMaxWidth: false } });
mermaid.run({ querySelector: ".mermaid" }).then(() => {
  const svg = document.querySelector(".mermaid svg");
  if (!svg) return;
  const nodes = new Map();
  for (const g of svg.querySelectorAll("g.node")) {
    const match = g.id.match(/^flowchart-(.+)-\\d+$/);
    if (match) nodes.set(match[1], g);
  }
  const labels = [...svg.querySelectorAll("g.edgeLabel")];
  const edges = [...svg.querySelectorAll("path.flowchart-link")].map((path) => {
    const [, from, to, index] = path.id.split("_");
    return { from, to, path, label: labels[Number(index)] };
  });
  const downstream = new Map();
  const upstream = new Map();
  for (const { from, to } of edges) {
    if (!downstream.has(from)) downstream.set(from, []);
    if (!upstream.has(to)) upstream.set(to, []);
    downstream.get(from).push(to);
    upstream.get(to).push(from);
  }
  const reach = (start, graph) => {
    const seen = new Set([start]);
    const stack = [start];
    while (stack.length) {
      for (const next of graph.get(stack.pop()) || []) {
        if (!seen.has(next)) { seen.add(next); stack.push(next); }
      }
    }
    return seen;
  };
  let selected = null;
  const focus = (id) => {
    selected = id;
    const keep = id === null ? null
      : new Set([...reach(id, downstream), ...reach(id, upstream)]);
    for (const [nodeId, g] of nodes) {
      g.classList.toggle("faded", keep !== null && !keep.has(nodeId));
      g.classList.toggle("selected", nodeId === id);
    }
    for (const edge of edges) {
      const shown = keep === null || (keep.has(edge.from) && keep.has(edge.to));
      edge.path.classList.toggle("faded", !shown);
      if (edge.label) edge.label.classList.toggle("faded", !shown);
    }
  };
  for (const [id, g] of nodes) {
    g.addEventListener("click", (event) => {
      event.stopPropagation();
      focus(selected === id ? null : id);
    });
  }
  svg.addEventListener("click", () => focus(null));
});
"""


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
<script>
// Embedded in another page (e.g. the docs): that page has the title and intro.
if (window.self !== window.top) document.documentElement.classList.add("embedded");
</script>
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
  .embedded h1, .embedded .lede, .embedded footer {{ display: none; }}
  .embedded main {{ padding-top: 8px; }}
  .hint {{ font-size: 13px; color: var(--muted); margin: 0 0 12px; }}
  .mermaid g.node {{ cursor: pointer; }}
  .mermaid g.node, .mermaid path.flowchart-link, .mermaid g.edgeLabel {{
    transition: opacity .15s; }}
  .mermaid .faded {{ opacity: .1; }}
  .mermaid g.node.selected > :first-child {{ stroke-width: 3px !important; }}
</style>
</head>
<body>
<main>
  <h1>Metric lineage</h1>
  <p class="lede">Which ingested data each maturity metric reads, and the functions
  applied on the way: <b>scaling</b> on the edges from data fields,
  <b>reconciliation</b> (in italics) inside each metric, combining its sources,
  and <b>aggregation</b> (in italics) inside each dimension.</p>
  <div class="legend">{swatches}</div>
  <p class="hint">Click any node to show only what it is connected to; click it
  again, or the background, to show everything.</p>
  <div class="card">
<div class="mermaid">
{html.escape(lineage_to_mermaid(lineage), quote=False)}</div>
  </div>
  <footer>Traced on:<ul>{datasets}</ul></footer>
</main>
<script>
{_FOCUS_SCRIPT}
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
