# Usage

## Installation

```bash
poetry install
```

## Command line

```bash
poetry run maturity-meter evaluate https://github.com/owner/repo \
  --doi 10.1000/example --biotools-id example
```

The result is printed as JSON. `-o result.json` also saves it, and
`--save-data data.json` saves the ingested data for reuse with
`--data data.json`. Missing or null sources, including FAIR-Checker in older
files, are fetched again.

FAIR-Checker evaluates the repository URL via its official API, separately
from resqui. The bundled resqui configuration runs RSFC, OEBFAIR, HowFairIs
and OpenSSF Scorecard checks corresponding to the
workbook's retained and provisional indicators. These tools provide individual
checks, not necessarily every subcheck of a composite workbook indicator.
They require Docker, image downloads, network access and (for some checks) a
GitHub token; HowFairIs installs Python tools. Runs can be much
slower; each plugin's resqui run has a 10-minute timeout. Re-run the evaluation
without supplying previously saved
`quality_checks` to collect the new results: `--data` reuses a supplied
assessment instead of running resqui again. Missing configured checks are
logged, along with failures reported by resqui; resqui may omit failed checks.
Resqui and its tools use the system temporary directory (or `TMPDIR` if set)
for clones and tool environments, so insufficient space can prevent an
assessment. Existing batch data files are skipped,
so use a new output directory to collect newly configured checks.

## Batch evaluation from CSV

Evaluate every tool in a CSV with `biotoolsID`, `homepage` (repository URL)
and `dois` columns. Multiple DOIs are comma-separated.

```bash
maturity-meter batch "results/bio.tools entries - github_gitlab_tools_with_publications.csv" \
  --output-dir results/batch
```

Add `--dry-run` to list and validate entries without running evaluations or
creating output. Ingested data is saved in `results/batch/raw/`, with CSV row
numbers and bio.tools IDs in the filenames, as soon as each tool is done. No
score files are saved. Existing data files are skipped and never overwritten,
so an interrupted batch continues where it stopped when run again; failed
evaluations do not leave a data file to be mistaken for a completed run. Use a
separate output directory for each CSV. Each tool's log is written to
`results/batch/logs/`, named like its data file; the terminal shows one line
per tool as it starts and finishes.

Several tools are evaluated at once (`--jobs`, or `MATURITY_METER_BATCH_JOBS`;
4 by default), so the quick,
network-bound sources of some tools overlap with the slow Docker checks of
others. The resqui checks of all tools share one limit on resqui processes:
`MATURITY_METER_RESQUI_PARALLEL`, by default one per configured plugin. Raise
`--jobs` (or `MATURITY_METER_BATCH_JOBS`) to keep Docker busy; lower `MATURITY_METER_RESQUI_PARALLEL` if Docker
runs short of memory or CPU. Requests to the public FAIR-Checker service are
sent one at a time, since simultaneous requests can mix up its results. With a
GitHub token, the batch checks GitHub's
rate limit before each GitHub tool and waits for the reset when fewer than 500
requests are left, instead of letting sources fail; without a token, most
GitHub tools will lack data.

GitHub links to releases, files or other paths inside a repository are skipped
rather than assuming their enclosing repository is the correct one. Invalid or
unsupported URLs and failed evaluations are reported, processing continues,
and the command returns a nonzero exit status if any errors occurred. GitLab
subgroup repository paths are supported. Individual evaluations may take
several minutes and require network access and Docker.

Create a spreadsheet from completed raw results with:

```bash
python scripts/metrics_report.py results/batch/raw/*.json -o results/batch/metrics.ods
```

## Comparing reported metrics

From a source checkout, create a LibreOffice Calc OpenDocument spreadsheet from one or more
saved ingestion files:

```bash
python scripts/metrics_report.py tool-a.json tool-b.json -o metrics.ods
```

The spreadsheet contains a metric-details sheet (metric name, source, identifier,
expected range and short description), and a comparison sheet with tools as rows
and source-qualified metric names as columns. A blank cell means that the input did not report a value; a
blank range means it is not specified. Values are copied without calculating
new metrics. Numeric and Boolean values remain typed spreadsheet cells; text
values remain text. The comparison sheet may require horizontal scrolling.

The report includes Lizard code metrics, resqui check outputs, GitHub/GitLab
stars, forks, open-issue and branch-protection fields, the scalar measurements
in the OpenEBench metrics record, bio.tools publication citation counts, and
OpenAlex citation counts and FWCI and Europe PMC citation counts and
open-access fields. The official FAIR-Checker API's reported numeric test
values appear under `FAIRChecker API`, separate from `FAIRChecker` outputs in
older resqui assessments, which were transformed to true/false/indeterminate.
When reporting saved data, a FAIR-Checker result without a usable test ID is
skipped with a warning identifying the file and result. Other identifiable
results are preserved; no metric is inferred for the skipped result.
The API's raw JSON-LD is saved as `fair_checker`; missing or failed assessments
are null. Existing `--data` files remain usable, and a supplied `fair_checker`
assessment is reused. The API receives the repository URL, including for GitLab
repositories, and may take up to 300 seconds to respond. Responses with missing
or duplicate test identifiers are rejected with a warning instead of assigning
scores to the wrong indicators. The report does not treat arbitrary repository
metadata as metrics.

For publication metrics, each source and metric has one column per tool. Its
cell contains a JSON list of reported values with DOI or PMID when available;
OpenEBench publication results also retain list positions and any year or title.
No values are summed or averaged. Other OpenEBench list entries without a DOI or
year are identified by their position, which may not represent the same item
across different records. Generic descriptions identify the reported field when
no more specific definition is available.
If a source reports multiple checks for the same indicator, their outputs,
processes, statuses and evidence are retained together as a JSON list in one
comparison cell.

Publication metrics retain their DOI (or PMID) so that distinct works are not
combined. OpenEBench list entries without a DOI or year are identified by their
position, which may not represent the same item across different records.

## Metric statistics PDF

Install the optional plotting dependency and pass the same saved JSON files used
for the spreadsheet:

```bash
poetry install --extras reports
poetry run python scripts/metrics_stats.py results/batch/raw/*.json -o results/batch/statistics.pdf
```

`poetry install` may replace an editable local resqui installation with the
locked version. If you use the local QualityPipelines fork, reinstall it with
`poetry run pip install -e ../QualityPipelines` after installing the extra.

Select one saved result per tool; duplicate bio.tools IDs are rejected rather
than counted twice. When an ID is absent, the repository URL identifies the
tool. Different bio.tools entries can share a repository and are counted
separately. The PDF has a distribution for each scalar metric,
including categorical values, and lists excluded metrics. Numeric histograms
count tools; boolean and categorical values are shown as frequency bars.
Grouped publication values and multiple checks in one cell are excluded from
both distributions and comparisons, as are mixed-type and non-finite metrics.
Missing values are not counted as zero.

The comparison sections show up to 20 numeric pairs ranked by signed Pearson
correlation and 20 boolean pairs ranked by exact agreement. Only tools
with both values are used. At least five overlapping tools are required by
default; `--min-overlap` changes this threshold (minimum three). Constant
numeric values cannot be correlated. Categorical and cross-type pairs are not
compared. Positional OpenEBench list entries are charted but not compared,
because the same position can mean different things for different tools.
High agreement can arise from imbalanced values, and correlation or
agreement does not establish that metrics measure the same thing. Review
source evidence before interpreting results.

## Lineage

To see which ingested data and helper functions (scaling, reconciliation, ...)
each metric and dimension uses, trace them on saved data:

```bash
poetry run maturity-meter lineage data.json other-tool.json -o lineage.json
```

The lineage is traced by running the metrics, so it always matches the code.
It only sees the code paths the data triggers; passing data from several tools
merges their coverage.

Add `--figure lineage.html` to draw it as a flow figure: ingested sources,
the fields read from them, the metrics and the dimensions. Field-to-metric
edges show the **scaling** applied, each metric shows its **reconciliation**
(how it combines its sources), and metric-to-dimension edges show the
**aggregation**. Use a `.mmd` file name to get the Mermaid source instead,
e.g. to embed it in Markdown.

Functions get their role from the `@role(...)` decorator in
`maturity_meter.components.utils.roles` (`"scaling"`, `"reconciliation"` or
`"aggregation"`); tag new helpers with it so they show up in the right place.

FAIR-Checker evaluates the repository URL via its official API, separately
from resqui. The bundled resqui configuration runs RSFC, OEBFAIR, HowFairIs
and OpenSSF Scorecard checks corresponding to the
workbook's retained and provisional indicators. These tools provide individual
checks, not necessarily every subcheck of a composite workbook indicator.
They require Docker, image downloads, network access and (for some checks) a
GitHub token; HowFairIs installs Python tools. Runs can be much
slower. To save time, each plugin's checks run in their own resqui process,
all plugins at once (set `MATURITY_METER_RESQUI_PARALLEL` to run fewer at a
time); each process has a 10-minute timeout. A plugin whose run fails is skipped and the other plugins' checks
are kept. Re-run the evaluation
without supplying previously saved
`quality_checks` to collect the new results: `--data` reuses a supplied
assessment instead of running resqui again. Missing configured checks are
logged, along with failures reported by resqui; resqui may omit failed checks.
Resqui and its tools use the system temporary directory (or `TMPDIR` if set)
for clones and tool environments, so insufficient space can prevent an
assessment. Existing batch data files are skipped,
so use a new output directory to collect newly configured checks.

## Batch evaluation from CSV

Evaluate every tool in a CSV with `biotoolsID`, `homepage` (repository URL)
and `dois` columns. Multiple DOIs are comma-separated.

```bash
maturity-meter batch "results/bio.tools entries - github_gitlab_tools_with_publications.csv" \
  --output-dir results/batch
```

Add `--dry-run` to list and validate entries without running evaluations or
creating output. Ingested data is saved in `results/batch/raw/`, with CSV row
numbers and bio.tools IDs in the filenames, as soon as each tool is done. No
score files are saved. Existing data files are skipped and never overwritten,
so an interrupted batch continues where it stopped when run again; failed
evaluations do not leave a data file to be mistaken for a completed run. Use a
separate output directory for each CSV. Each tool's log is written to
`results/batch/logs/`, named like its data file; the terminal shows one line
per tool as it starts and finishes.

Several tools are evaluated at once (`--jobs`, or `MATURITY_METER_BATCH_JOBS`;
4 by default), so the quick,
network-bound sources of some tools overlap with the slow Docker checks of
others. The resqui checks of all tools share one limit on resqui processes:
`MATURITY_METER_RESQUI_PARALLEL`, by default one per configured plugin. Raise
`--jobs` (or `MATURITY_METER_BATCH_JOBS`) to keep Docker busy; lower `MATURITY_METER_RESQUI_PARALLEL` if Docker
runs short of memory or CPU. Requests to the public FAIR-Checker service are
sent one at a time, since simultaneous requests can mix up its results. With a
GitHub token, the batch checks GitHub's
rate limit before each GitHub tool and waits for the reset when fewer than 500
requests are left, instead of letting sources fail; without a token, most
GitHub tools will lack data.

GitHub links to releases, files or other paths inside a repository are skipped
rather than assuming their enclosing repository is the correct one. Invalid or
unsupported URLs and failed evaluations are reported, processing continues,
and the command returns a nonzero exit status if any errors occurred. GitLab
subgroup repository paths are supported. Individual evaluations may take
several minutes and require network access and Docker.

Create a spreadsheet from completed raw results with:

```bash
python scripts/metrics_report.py results/batch/raw/*.json -o results/batch/metrics.ods
```

## Comparing reported metrics

From a source checkout, create a LibreOffice Calc OpenDocument spreadsheet from one or more
saved ingestion files:

```bash
python scripts/metrics_report.py tool-a.json tool-b.json -o metrics.ods
```

The spreadsheet contains a metric-details sheet (metric name, source, identifier,
expected range and short description), and a comparison sheet with tools as rows
and source-qualified metric names as columns. A blank cell means that the input did not report a value; a
blank range means it is not specified. Values are copied without calculating
new metrics. Numeric and Boolean values remain typed spreadsheet cells; text
values remain text. The comparison sheet may require horizontal scrolling.

The report includes Lizard code metrics, resqui check outputs, GitHub/GitLab
stars, forks, open-issue and branch-protection fields, the scalar measurements
in the OpenEBench metrics record, bio.tools publication citation counts, and
OpenAlex citation counts and FWCI and Europe PMC citation counts and
open-access fields. Direct FAIR-Checker scores are reported separately from
legacy resqui FAIRChecker outputs. It does not treat arbitrary repository
metadata as metrics.
For publication metrics, each source and metric has one column per tool. Its
cell contains a JSON list of reported values with DOI or PMID when available;
OpenEBench publication results also retain list positions and any year or title.
No values are summed or averaged. Other OpenEBench list entries without a DOI or
year are identified by their position, which may not represent the same item
across different records. Generic descriptions identify the reported field when
no more specific definition is available.
If a source reports multiple checks for the same indicator, their outputs,
processes, statuses and evidence are retained together as a JSON list in one
comparison cell.

## Web API

```bash
poetry run maturity-meter-serve
```

`POST /evaluate` with a JSON body returns the maturity result:

```json
{"repository": "https://github.com/owner/repo", "dois": [], "biotools_id": null}
```

Only `repository` is required.

## Library

```python
import asyncio

from maturity_meter import EvaluationRequest, evaluate_maturity

request = EvaluationRequest(repository="https://github.com/owner/repo")
result = asyncio.run(evaluate_maturity(request))
```

## Supplying data you already have

If another tool already has some of the data (for example a clone's metadata or
the bio.tools record), pass it in: whatever is supplied is used as-is, and
everything missing is fetched. Use the `data` field of `EvaluationRequest`, the
`data` key in the API body, or `--data file.json` on the command line. Any
subset works, including none.

```json
{
  "repository": {"...": "raw GitHub or GitLab ingestor output"},
  "biotools": {"...": "raw bio.tools entry"},
  "europe_pmc": {"10.1000/abc": {"...": "record"}},
  "openalex": {"https://doi.org/10.1000/abc": {"...": "work"}}
}
```

The other keys are `openebench`, `quality_checks`, `rsec` and `code_metrics`
(the repository is cloned once per evaluation, and only if `quality_checks`
or `code_metrics` is not supplied). `europe_pmc` and
`openalex` are keyed by DOI (in any common form): DOIs in `dois` without a
supplied record are fetched, and supplied DOIs not in `dois` are kept. `edam`
works the same way, keyed by EDAM format IRI.

## Functions

- **Evaluate maturity** of a repository: statistical calculation, data
  analysis, quantification (input: data reference; output: matrix).
- **Visualise maturity**: input matrix; output plot.
