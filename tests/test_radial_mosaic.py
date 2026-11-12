"""Tests for the radial mosaic of an evaluation."""

import shutil

import pytest

from maturity_meter.models import DimensionResult, Evaluation, MetricResult
from maturity_meter.services.radial_mosaic import components, render_svg, viz_dir

EMPTY = DimensionResult(value=None)
EVALUATION = Evaluation(
    compatibility=EMPTY,
    fairness=DimensionResult(
        value=0.5,
        metrics=[
            MetricResult(name="has_license", value=1.0),
            MetricResult(name="star_count", value=0.0),
            MetricResult(name="doi", value=None),
            MetricResult(name="citations", value=0.5),
        ],
    ),
    maintainability=EMPTY,
    scientific_impact=DimensionResult(
        value=0.04, metrics=[MetricResult(name="citation_count", value=0.04)]
    ),
    security=EMPTY,
    sustainability=EMPTY,
)


def test_dimension_rays():
    """Score is the ring, coverage the opacity, one colour; all six are drawn."""
    rays = components(EVALUATION)

    assert [(r["name"], r["ring"], round(r["opacity"], 3)) for r in rays] == [
        ("compatibility", 1, 0.1),
        ("fairness", 5, 0.775),
        ("maintainability", 1, 0.1),
        ("scientific impact", 1, 1.0),
        ("security", 1, 0.1),
        ("sustainability", 1, 0.1),
    ]
    assert len({r["categoryId"] for r in rays}) == 1
    assert [r.get("value") for r in rays] == [None, "50%", None, "4%", None, None]


@pytest.mark.skipif(
    shutil.which("node") is None
    or not (viz_dir() / "node_modules" / "viz-mosaic").exists(),
    reason="needs Node and `npm install --prefix viz`",
)
def test_render_svg():
    """viz-mosaic renders the dimensions, with their scores, as an SVG."""
    svg = render_svg(EVALUATION)

    assert 'data-component="fairness"' in svg
    assert ">50%</text>" in svg
