"""Guard that the synthetic lineage probes exercise every metric."""

from pathlib import Path

from maturity_meter.models import IngestedData
from maturity_meter.services.lineage import trace_lineage
from maturity_meter.services.processing import score

PROBES = Path(__file__).parent / "fixtures" / "lineage"


def test_probes_exercise_every_metric():
    """Full probes assess every metric, and every metric records reads.

    If this fails after adding a metric or source, extend the probes in
    ``tests/fixtures/lineage`` so the lineage covers it.
    """
    full = [IngestedData.load(PROBES / f"probe_{h}.json") for h in ("github", "gitlab")]
    for data in full:
        maturity = score(data).maturity
        not_assessed = [
            metric.name
            for dimension in type(maturity).model_fields
            for metric in getattr(maturity, dimension).metrics
            if metric.value is None
        ]
        assert not not_assessed, not_assessed

    lineage = trace_lineage(IngestedData.load(p) for p in sorted(PROBES.glob("*.json")))
    without_reads = [
        name
        for dimension in lineage.dimensions.values()
        for name, metric in dimension.metrics.items()
        if not metric.reads
    ]
    assert not without_reads, without_reads


def test_overview_covers_every_metric_with_its_weight():
    """Every traced metric has a weight and appears in the overview, linked."""
    from maturity_meter.services.overview import overview_markdown

    lineage = trace_lineage(IngestedData.load(p) for p in sorted(PROBES.glob("*.json")))
    unweighted = [
        f"{dimension}.{name}"
        for dimension, dim in lineage.dimensions.items()
        for name, metric in dim.metrics.items()
        if metric.weight is None
    ]
    assert not unweighted, unweighted
    page = overview_markdown(lineage, repository="https://example.org/repo", ref="abc")
    missing = [
        name
        for dim in lineage.dimensions.values()
        for name in dim.metrics
        if f"[`{name}`](https://example.org/repo/blob/abc/src/" not in page
    ]
    assert not missing, missing
