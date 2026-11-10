# Maturity meter

[![CI](https://github.com/bio-tools/maturity-meter/actions/workflows/tests.yml/badge.svg)](https://github.com/bio-tools/maturity-meter/actions/workflows/tests.yml)
[![Documentation](https://img.shields.io/badge/docs-online-blue?labelColor=gray)](https://bio-tools.github.io/maturity-meter)
[![Usage](https://img.shields.io/badge/usage-guide-blue?labelColor=gray)](https://github.com/bio-tools/maturity-meter/blob/HEAD/docs/usage.md)
[![License](https://img.shields.io/badge/license-view-blue?labelColor=gray)](https://github.com/bio-tools/maturity-meter/blob/HEAD/LICENSE)
![Tool Type](https://img.shields.io/badge/tool%20type-Command--line%20tool%20%7C%20Library%20%7C%20Web%20API-blue?labelColor=gray)

Automated maturity model for research software tools

Homepage: https://bio-tools.github.io/maturity-meter

## Purpose

This project aims to develop a new, automated, research software maturity model for tools in GitHub or GitLab. The project evaluates whether automated maturity (e.g., documentation quality, FAIR compliance, maintenance, and reuse signals) assessment can provide a scalable and informative complement to manual maturity annotation and assign up-to-date maturity levels.

As a long-term goal, the maturity model will become part of software disambiguation that goes beyond names, descriptions and topics, allowing for more fine-grained searchability among tools with similar functionality, building on the wealth of metadata in the Research Software Ecosystem to assist researchers searching for and making informed selections of software tools.

The project combines software metadata from bio.tools and other services of the Research Software Ecosystem, including OpenEBench, repository metadata from code hosting platforms, publication metadata from Europe PMC, and static code analysis using open-source software adapting and building on an automated maturity model recently developed in the more narrowly scoped TDCC-LSH “FAIR Toolbox” project in the Netherlands.

## Topics

- [Open science](http://edamontology.org/topic_4010)
- [Software management](http://edamontology.org/topic_4047)
- [Software engineering](http://edamontology.org/topic_3372)

## Installation

Install from a source checkout:

```bash
poetry install
```

## Usage

```bash
poetry run maturity-meter evaluate https://github.com/owner/repo
```

The result is printed as JSON; add `-o result.json` to save it. Use
`--save-data data.json` to save the fetched data, and `--data data.json` to
re-score it later without fetching anything again.

## Functions

<details>
<summary>Statistical calculation, Data analysis, Quantification</summary>

```yaml
# biotools-function
operation:
- term: "Statistical calculation"
  uri: "http://edamontology.org/operation_2238"
- term: "Data analysis"
  uri: "http://edamontology.org/operation_2945"
- term: "Quantification"
  uri: "http://edamontology.org/operation_3799"
input:
- data:
    term: "Data reference"
    uri: "http://edamontology.org/data_2093"
output:
- data:
    term: "Matrix"
    uri: "http://edamontology.org/data_2082"
note: "Evaluate maturity of a given repository"
```

</details>

<details>
<summary>Visualisation</summary>

```yaml
# biotools-function
operation:
- term: "Visualisation"
  uri: "http://edamontology.org/operation_0337"
input:
- data:
    term: "Matrix"
    uri: "http://edamontology.org/data_2082"
output:
- data:
    term: "Plot"
    uri: "http://edamontology.org/data_2884"
note: "Plot the resulting maturity"
```

</details>

## Documentation

Read the [project documentation](https://bio-tools.github.io/maturity-meter).

- User guide: installation, configuration, usage, and examples
- Developer guide: development, tests, contribution, and reference

## Access

**Access type:** free.

## Development

Set up the development environment with:

```bash
poetry install --all-extras
```
Run the configured checks:

```bash
poetry run ruff format --check .
poetry run ruff check .
poetry run mypy src
poetry run pytest
```
See [`CONTRIBUTING.md`](CONTRIBUTING.md) for the contribution and code-review policy.

## Citation

If you use this software, cite it using [`CITATION.cff`](CITATION.cff).

## Legal and Licensing

This project is licensed under `https://spdx.org/licenses/Apache-2.0.html`. See `LICENSE` for the full license text.

<!-- rs-files-templates:README:end -->
<!-- Add project-specific README content below this line; it is preserved when the generated README is refreshed. -->
