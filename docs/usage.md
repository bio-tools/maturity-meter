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
