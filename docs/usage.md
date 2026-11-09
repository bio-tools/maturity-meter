# Usage

## Installation

```bash
poetry install
```

## Command line

```bash
poetry run maturity-meter evaluate
```

## Web API

```bash
poetry run maturity-meter-serve
```

`GET /evaluate` returns the maturity result.

## Library

```python
from maturity_meter import evaluate_maturity

result = evaluate_maturity()
```

## Functions

- **Evaluate maturity** of a repository: statistical calculation, data
  analysis, quantification (input: data reference; output: matrix).
- **Visualise maturity**: input matrix; output plot.
