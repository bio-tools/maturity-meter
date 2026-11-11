# Metric lineage

The lineage shows, for every maturity metric, which ingested data it reads
and which functions it applies:

- **sources → fields**: the ingested data sources and the fields read from
  them;
- **fields → metrics**: labelled with the **scaling** applied to the data;
- **metrics**: show their **reconciliation** (how they combine several
  sources) in italics;
- **dimensions**: show their **aggregation** (how they combine their metrics
  into the dimension's score) in italics.

Click any node to show only what it is connected to: for a metric, the fields
and sources it reads and its dimension; for a source, every field, metric and
dimension that depends on it. Click it again, or the background, to show
everything.

It is generated from the code itself: the metrics are run on synthetic
*probe* data (`tests/fixtures/lineage`) that exercises every code path, and
each field read and helper call is recorded. It is not tied to any particular
evaluation, and it is regenerated on every documentation build, so it always
matches the code.

<iframe src="lineage/lineage.html" title="Metric lineage figure"
        style="width: 100%; height: 1200px; border: 1px solid #e2e8f0; border-radius: 8px;"></iframe>

[Open the figure on its own page](lineage/lineage.html) ·
[Download the lineage as JSON](lineage/lineage.json)

## Regenerating locally

```bash
mkdir -p docs/lineage
poetry run maturity-meter lineage tests/fixtures/lineage/*.json \
  -o docs/lineage/lineage.json --figure docs/lineage/lineage.html
```

When a new metric or ingestion source is added, extend the probes so it is
covered; `tests/test_lineage.py` fails until every metric is fully exercised.
