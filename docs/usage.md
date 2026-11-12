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
`--save-data data.json` saves the ingested data, which can be re-scored later
without fetching anything: `--data data.json`.

The bundled resqui configuration includes the eight FAIR-Checker checks
supported by the bio-tools QualityPipelines fork. They require that fork's
`FAIRChecker` plugin and a running Docker daemon; FAIR-Checker evaluates the
repository URL. The configuration also runs RSFC, OEBFAIR, SuperLinter,
ASTMetrics, HowFairIs and OpenSSF Scorecard checks corresponding to the
workbook's retained and provisional indicators. These tools provide individual
checks, not necessarily every subcheck of a composite workbook indicator.
They require Docker, image downloads, network access and (for some checks) a
GitHub token; ASTMetrics and HowFairIs install Python tools. Runs can be much
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

From a source checkout, run evaluations sequentially for a CSV with
`biotoolsID`, `homepage` (repository URL) and `dois` columns. Multiple DOIs
are comma-separated. Use the executable from the environment containing the
local resqui fork:

```bash
python scripts/evaluate_batch.py "results/bio.tools entries - github_gitlab_tools_with_publications.csv" \
  --output-dir results/batch --executable ../QualityPipelines/.venv/bin/maturity-meter
```

Add `--dry-run` to list and validate entries without running evaluations or
creating output. Ingested data is saved in `results/batch/raw/`, with CSV row
numbers and bio.tools IDs in the filenames. No score files are saved. Existing
data files are skipped and never overwritten; failed evaluations do not leave
a data file to be mistaken for a completed run. Use a separate output directory
for each CSV.

GitHub links to releases, files or other paths inside a repository are skipped
rather than assuming their enclosing repository is the correct one. Invalid or
unsupported URLs and failed evaluations are reported, processing continues,
and the script returns a nonzero exit status if any errors occurred. GitLab
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
open-access fields. It does not treat arbitrary repository metadata as metrics.

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

The bundled resqui configuration includes the eight FAIR-Checker checks
supported by the bio-tools QualityPipelines fork. They require that fork's
`FAIRChecker` plugin and a running Docker daemon; FAIR-Checker evaluates the
repository URL. The configuration also runs RSFC, OEBFAIR, SuperLinter,
ASTMetrics, HowFairIs and OpenSSF Scorecard checks corresponding to the
workbook's retained and provisional indicators. These tools provide individual
checks, not necessarily every subcheck of a composite workbook indicator.
They require Docker, image downloads, network access and (for some checks) a
GitHub token; ASTMetrics and HowFairIs install Python tools. Runs can be much
slower. To save time, each plugin's checks run in their own resqui process,
all plugins at once (set `MATURITY_METER_RESQUI_PARALLEL` to run fewer at a
time); the repository is cloned once and shared by the processes, and
each process has a 10-minute timeout. A plugin whose run fails is skipped and the other plugins' checks
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

From a source checkout, run evaluations sequentially for a CSV with
`biotoolsID`, `homepage` (repository URL) and `dois` columns. Multiple DOIs
are comma-separated. Use the executable from the environment containing the
local resqui fork:

```bash
python scripts/evaluate_batch.py "results/bio.tools entries - github_gitlab_tools_with_publications.csv" \
  --output-dir results/batch --executable ../QualityPipelines/.venv/bin/maturity-meter
```

Add `--dry-run` to list and validate entries without running evaluations or
creating output. Ingested data is saved in `results/batch/raw/`, with CSV row
numbers and bio.tools IDs in the filenames. No score files are saved. Existing
data files are skipped and never overwritten; failed evaluations do not leave
a data file to be mistaken for a completed run. Use a separate output directory
for each CSV.

GitHub links to releases, files or other paths inside a repository are skipped
rather than assuming their enclosing repository is the correct one. Invalid or
unsupported URLs and failed evaluations are reported, processing continues,
and the script returns a nonzero exit status if any errors occurred. GitLab
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
open-access fields. It does not treat arbitrary repository metadata as metrics.
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
(supplying `code_metrics` avoids cloning the repository). `europe_pmc` and
`openalex` are keyed by DOI (in any common form): DOIs in `dois` without a
supplied record are fetched, and supplied DOIs not in `dois` are kept. `edam`
works the same way, keyed by EDAM format IRI.

## Functions

- **Evaluate maturity** of a repository: statistical calculation, data
  analysis, quantification (input: data reference; output: matrix).
- **Visualise maturity**: input matrix; output plot.
