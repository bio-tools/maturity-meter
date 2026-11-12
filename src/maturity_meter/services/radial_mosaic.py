"""Radial mosaic of an :class:`Evaluation`, drawn by viz-mosaic.

Each ray is a dimension or a metric: its length (``ring``) is the score and its
opacity is the coverage. Dimension rays share one colour, so opacities compare;
metric rays are coloured and grouped by their dimension.
Opacity runs from ``MIN_OPACITY`` (coverage 0) to 1, so every dimension (or
metric) stays visible; an unassessed one sits faintly at the first ring. The
score is written across the tip of each assessed ray (viz-mosaic's ``value``).

The SVG is rendered by https://github.com/thatmariia/viz-mosaic through the
small Node script in ``viz/`` (install it once with ``npm install --prefix viz``;
``MATURITY_METER_VIZ_DIR`` points elsewhere, e.g. in the container image).
"""

import base64
import json
import subprocess
from pathlib import Path
from typing import Literal

from maturity_meter.config import get_settings
from maturity_meter.models import Evaluation

RING_LEVELS = 10
MIN_OPACITY = 0.1
# Labels use DM Sans, embedded from the font viz-mosaic ships with its demo, so
# the SVG looks the same where the font is not installed.
FONT_FAMILY = "DM Sans"
FONT_FILE = "node_modules/viz-mosaic/demo/assets/fonts/dmsans.woff2"
_CHECKOUT_VIZ_DIR = Path(__file__).resolve().parents[3] / "viz"
_CATEGORY = "maturity"


def viz_dir() -> Path:
    """Folder with the Node renderer: ``MATURITY_METER_VIZ_DIR``, else ``viz/``."""
    return get_settings().viz_dir or _CHECKOUT_VIZ_DIR


def ring(score: float | None) -> int:
    """Ray length for a score in [0, 1]: 1 to ``RING_LEVELS`` (1 if unassessed)."""
    return max(1, round((score or 0) * RING_LEVELS))


def components(
    evaluation: Evaluation, per: Literal["dimension", "metric"] = "dimension"
) -> list[dict]:
    """viz-mosaic components: one per dimension or one per metric.

    Parameters
    ----------
    evaluation : Evaluation
        Result of an evaluation.
    per : {"dimension", "metric"}, default="dimension"
        What each ray stands for. A dimension's opacity is its coverage (share
        of its metrics assessed); a metric's is 1 if assessed, else 0. Metric
        rays take their dimension as category (colour), in dimension order.

    Returns
    -------
    list[dict]
        Components for ``renderRadialMosaic``.
    """
    rays = []  # (name, score, coverage, category)
    for name, dim in evaluation:
        if per == "dimension":
            rays.append((name, dim.value, dim.coverage, _CATEGORY))
        else:
            rays += [
                (m.name, m.value, float(m.value is not None), _title(name))
                for m in dim.metrics
            ]
    return [
        {
            "name": _title(name),
            "ring": ring(score),
            "opacity": MIN_OPACITY + (1 - MIN_OPACITY) * coverage,
            "categoryId": category,
            **({} if score is None else {"value": f"{score:.0%}"}),
        }
        for name, score, coverage, category in rays
    ]


def _title(name: str) -> str:
    return name.replace("_", " ").lower()


def render_svg(
    evaluation: Evaluation,
    per: Literal["dimension", "metric"] = "dimension",
    title: str = "Maturity",
) -> str:
    """Render the evaluation as a radial mosaic SVG.

    Parameters
    ----------
    evaluation : Evaluation
        Result of an evaluation.
    per : {"dimension", "metric"}, default="dimension"
        One ray per dimension or per metric (see :func:`components`).
    title : str, default="Maturity"
        Accessible title of the SVG.

    Returns
    -------
    str
        The SVG markup.

    Raises
    ------
    RuntimeError
        If Node or viz-mosaic is missing, or rendering fails.
    """
    options = {
        "title": title,
        "palette": "palette-2",
        "keepInputOrder": True,  # dimension order; groups metrics by dimension
        "scaleRadialLabels": True,
        "fontFamily": FONT_FAMILY,
    }
    folder = viz_dir()
    if (font_file := folder / FONT_FILE).exists():
        font = base64.b64encode(font_file.read_bytes()).decode()
        options["fontSource"] = f"data:font/woff2;base64,{font}"
    payload = {"components": components(evaluation, per), "options": options}
    try:
        done = subprocess.run(
            ["node", str(folder / "radial.mjs")],
            input=json.dumps(payload),
            capture_output=True,
            text=True,
            check=False,
        )
    except FileNotFoundError as error:
        raise RuntimeError("Node.js (>= 20) is needed to render the mosaic.") from error
    if done.returncode != 0:
        raise RuntimeError(
            f"Rendering failed (did you run `npm install` in {folder}?):\n"
            + done.stderr
        )
    return done.stdout
