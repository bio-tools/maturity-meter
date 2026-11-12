#!/usr/bin/env python3
"""Create an ODS comparison of reported metrics in saved ingestion data."""

import argparse
import json
import re
import sys
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET
from zipfile import ZIP_DEFLATED, ZIP_STORED, ZipFile


@dataclass(frozen=True, order=True)
class Metric:
    source: str
    identifier: str
    expected_range: str = ""


REPOSITORY_METRICS = {
    "stargazers_count": ("stars", ">= 0"),
    "star_count": ("stars", ">= 0"),
    "forks_count": ("forks", ">= 0"),
}
CODE_RANGES = {
    "files": ">= 0",
    "functions": ">= 0",
    "total_nloc": ">= 0",
    "total_ccn": ">= 0",
    "avg_ccn": ">= 0",
    "nloc_per_file": ">= 0",
    "duplicate_rate": "0–100%",
}
PUBLICATION_FIELDS = {
    "openalex": {"cited_by_count": ">= 0", "fwci": ">= 0"},
    "europe_pmc": {"citedByCount": ">= 0", "isOpenAccess": "Y / N"},
}
BOOLEAN_CHECKS = {
    "https://w3id.org/everse/i/indicators/software_has_citation",
    "https://w3id.org/everse/i/indicators/no_leaked_credentials",
    "https://w3id.org/everse/i/indicators/software_has_license",
    "https://w3id.org/everse/i/indicators/dependency_management",
    "https://w3id.org/everse/i/indicators/has_ci-tests",
    "https://w3id.org/everse/i/indicators/human_code_review_requirement",
}
METRIC_DESCRIPTIONS = {
    "stars": "Number of repository stars.",
    "forks": "Number of repository forks.",
    "open_issues": "Number of open issues, excluding pull requests.",
    "default_branch_protected": "Whether the default branch is protected.",
    "files": "Number of files analyzed by Lizard.",
    "functions": "Number of functions analyzed by Lizard.",
    "total_nloc": "Total lines of code in analyzed functions.",
    "total_ccn": "Total cyclomatic complexity of analyzed functions.",
    "avg_ccn": "Average cyclomatic complexity per function.",
    "nloc_per_file": "Function lines of code per analyzed file.",
    "duplicate_rate": "Percentage of duplicate code reported by Lizard.",
    "publication.citationCount": "Citation count reported for each publication.",
    "publication.cited_by_count": "Citation count reported for each publication.",
    "publication.citedByCount": "Citation count reported for each publication.",
    "publication.fwci": "Field-weighted citation impact for each publication.",
    "publication.isOpenAccess": "Open-access status reported for each publication.",
    "project.publications[].entries[].cit_count": (
        "Citation count for each publication."
    ),
    "project.publications[].entries[].ref_count": (
        "Reference count for each publication."
    ),
    "project.publications[].entries[].citations[].count": (
        "Citation count by year for each publication."
    ),
    "project.website.access_time": "Website response time reported by OpenEBench.",
    "project.website.operational": "Website HTTP status reported by OpenEBench.",
    "project.website.last_month_access.uptime_days": (
        "Number of days the website was available in the last month."
    ),
    "project.website.last_month_access.downtime_days": (
        "Number of days the website was unavailable in the last month."
    ),
    "software_has_citation": "Whether a valid citation file was found.",
    "no_leaked_credentials": "Whether the credential scan found no leaks.",
    "software_has_license": "Whether a license file was found.",
    "dependency_management": "Whether dependency update tooling was detected.",
    "has_ci-tests": "Whether changes were checked by CI tests.",
    "human_code_review_requirement": "Whether changes received human review.",
    "F1A": "FAIR-Checker result for unique identifiers.",
    "F1B": "FAIR-Checker result for persistent identifiers.",
    "F2A": "FAIR-Checker result for structured metadata.",
    "F2B": "FAIR-Checker result for shared metadata vocabularies.",
    "I1": "FAIR-Checker result for machine-readable format.",
    "I2": "FAIR-Checker result for shared ontologies.",
    "I3": "FAIR-Checker result for external links.",
    "R11": "FAIR-Checker result for license metadata.",
}
NAMESPACES = {
    "office": "urn:oasis:names:tc:opendocument:xmlns:office:1.0",
    "text": "urn:oasis:names:tc:opendocument:xmlns:text:1.0",
    "table": "urn:oasis:names:tc:opendocument:xmlns:table:1.0",
    "style": "urn:oasis:names:tc:opendocument:xmlns:style:1.0",
    "fo": "urn:oasis:names:tc:opendocument:xmlns:xsl-fo-compatible:1.0",
    "manifest": "urn:oasis:names:tc:opendocument:xmlns:manifest:1.0",
}
for prefix, uri in NAMESPACES.items():
    ET.register_namespace(prefix, uri)


def tag(prefix: str, name: str) -> str:
    return f"{{{NAMESPACES[prefix]}}}{name}"


def scalar(value: Any) -> str | int | float | bool:
    if isinstance(value, (str, int, float, bool)):
        return value
    raise ValueError(f"Expected a scalar metric value, got {type(value).__name__}")


def metric_name(metric: Metric) -> str:
    identifier = metric.identifier.rsplit("/", 1)[-1]
    fair_names = {
        "F1A": "Unique identifiers",
        "F1B": "Persistent identifiers",
        "F2A": "Structured metadata",
        "F2B": "Shared metadata vocabularies",
        "I1": "Machine-readable format",
        "I2": "Shared ontologies",
        "I3": "External links",
        "R11": "License metadata",
    }
    if identifier in fair_names and metric.source in ("FAIRChecker", "FAIRChecker API"):
        return fair_names[identifier]
    return re.sub(r"(?<=[a-z])(?=[A-Z])", " ", identifier).replace("_", " ")


def metric_description(metric: Metric) -> str:
    key = metric.identifier.rsplit("/", 1)[-1]
    return METRIC_DESCRIPTIONS.get(
        key, f"{metric.source} reported value for {metric_name(metric)}."
    )


def reported_metrics(data: dict[str, Any]) -> dict[Metric, str | int | float | bool]:
    """Extract reported values without calculating or inferring measurements."""
    result: dict[Metric, str | int | float | bool] = {}
    publication_values: dict[Metric, list[dict[str, Any]]] = {}

    def add(source: str, identifier: str, value: Any, expected_range: str = "") -> None:
        if value is None:
            return
        metric = Metric(source, identifier, expected_range)
        reported = scalar(value)
        if metric in result and result[metric] != reported:
            raise ValueError(f"Conflicting values for {source}: {identifier}")
        result[metric] = reported

    def add_publication(
        source: str,
        identifier: str,
        value: Any,
        context: dict[str, Any],
        expected_range: str = "",
    ) -> None:
        if value is not None:
            metric = Metric(source, identifier, expected_range)
            publication_values.setdefault(metric, []).append(
                {**context, "value": scalar(value)}
            )

    request = data.get("request") or {}
    if not isinstance(request, dict) or not isinstance(request.get("repository"), str):
        raise ValueError("Missing request.repository in saved ingestion data")
    repository = data.get("repository") or {}
    if not isinstance(repository, dict):
        raise ValueError("repository must be an object")
    host = (
        "GitHub"
        if request["repository"].split("/")[2].lower() == "github.com"
        else "GitLab"
    )
    repo = repository.get("repo") or {}
    for field, (identifier, expected_range) in REPOSITORY_METRICS.items():
        if field in repo:
            add(host, identifier, repo[field], expected_range)
    add(host, "open_issues", repository.get("open_issues"), ">= 0")
    add(
        host,
        "default_branch_protected",
        repository.get("default_branch_protected"),
        "true / false",
    )

    for field, value in (data.get("code_metrics") or {}).items():
        add("Lizard", field, value, CODE_RANGES.get(field, ""))

    quality = data.get("quality_checks") or {}
    grouped_checks: dict[Metric, list[dict[str, Any]]] = {}
    for check in quality.get("checks", []):
        indicator = check.get("assessesIndicator", {}).get("@id")
        source = check.get("checkingSoftware", {}).get("name")
        if not indicator or not source:
            raise ValueError("A quality check is missing its indicator ID or source")
        value = check.get("output")
        expected = "true / false" if indicator in BOOLEAN_CHECKS else ""
        if value is not None:
            metric = Metric(source, indicator, expected)
            grouped_checks.setdefault(metric, []).append(
                {
                    "output": scalar(value),
                    "process": check.get("process"),
                    "status": check.get("status", {}).get("@id"),
                    "evidence": check.get("evidence"),
                }
            )
    for metric, checks in grouped_checks.items():
        result[metric] = (
            checks[0]["output"]
            if len(checks) == 1
            else json.dumps(checks, ensure_ascii=False)
        )

    # Keep direct API scores distinct from resqui's derived true/false outputs.
    for node in data.get("fair_checker") or []:
        if "https://w3id.org/ftr#TestResult" not in node.get("@type", []):
            continue
        tests = node.get("https://w3id.org/ftr#outputFromTest", [])
        values = node.get("http://www.w3.org/ns/prov#value", [])
        if not isinstance(tests, list) or not isinstance(values, list):
            raise ValueError("Invalid FAIR-Checker test result")
        if len(tests) != 1 or len(values) > 1:
            raise ValueError("FAIR-Checker test result has ambiguous test or value")
        test = tests[0].get("@id") if isinstance(tests[0], dict) else None
        if (
            not isinstance(test, str)
            or "/test/" not in test
            or test.rsplit("/test/", 1)[-1] in ("", "None")
        ):
            raise ValueError("FAIR-Checker test result has no usable test ID")
        if values:
            if not isinstance(values[0], dict) or "@value" not in values[0]:
                raise ValueError("FAIR-Checker test result has an invalid value")
            add("FAIRChecker API", test.rsplit("/test/", 1)[-1], values[0]["@value"])

    # OpenEBench's metrics document is already a source-specific metric record.
    # DOI/year keys preserve the identity of publication and annual observations.
    def openebench(
        value: Any, path: str, context: dict[str, Any] | None = None
    ) -> None:
        if isinstance(value, dict):
            if context is not None:
                context = {
                    **context,
                    **{
                        key: value[key]
                        for key in ("doi", "pmid", "title", "year")
                        if value.get(key) is not None
                    },
                }
            for key, child in value.items():
                if key.startswith("@") or key in {"doi", "pmid", "title", "year"}:
                    continue
                child_path = f"{path}.{key}" if path else key
                child_context = {} if child_path == "project.publications" else context
                openebench(child, child_path, child_context)
        elif isinstance(value, list):
            for index, child in enumerate(value):
                if context is not None:
                    openebench(
                        child,
                        f"{path}[]",
                        {**context, f"{path}.index": index},
                    )
                    continue
                if isinstance(child, dict) and child.get("doi"):
                    label = f"doi={child['doi']}"
                elif isinstance(child, dict) and child.get("year") is not None:
                    label = f"year={child['year']}"
                else:
                    label = str(index)
                openebench(child, f"{path}[{label}]", context)
        elif value is not None:
            if context is None:
                add("OpenEBench", path, value)
            else:
                add_publication("OpenEBench", path, value, context)

    openebench((data.get("openebench") or {}).get("metrics") or {}, "")

    publications = (data.get("biotools") or {}).get("publication") or []
    for index, publication in enumerate(publications):
        count = (publication.get("metadata") or {}).get("citationCount")
        context = (
            {"doi": publication["doi"]}
            if publication.get("doi")
            else (
                {"pmid": publication["pmid"]}
                if publication.get("pmid")
                else {"index": index}
            )
        )
        add_publication(
            "bio.tools", "publication.citationCount", count, context, ">= 0"
        )

    for source, fields in PUBLICATION_FIELDS.items():
        for doi, record in (data.get(source) or {}).items():
            if record is not None:
                for field, expected_range in fields.items():
                    add_publication(
                        source,
                        f"publication.{field}",
                        record.get(field),
                        {"doi": doi},
                        expected_range,
                    )
    for metric, values in publication_values.items():
        result[metric] = json.dumps(values, ensure_ascii=False)
    return result


def element(
    parent: ET.Element, prefix: str, name: str, **attributes: str
) -> ET.Element:
    return ET.SubElement(parent, tag(prefix, name), attributes)


def paragraph(parent: ET.Element, text: str) -> None:
    element(parent, "text", "p").text = text


def table(
    parent: ET.Element,
    name: str,
    rows: list[list[str | int | float | bool | None]],
) -> None:
    node = element(parent, "table", "table", **{tag("table", "name"): name})
    widths = (
        [
            "metric-name",
            "metric-source",
            "metric-identifier",
            "metric-range",
            "metric-description",
        ]
        if name == "Metric details"
        else ["tool", *(["metric"] * (len(rows[0]) - 1))]
    )
    for width in widths:
        element(node, "table", "table-column", **{tag("table", "style-name"): width})
    for values in rows:
        row = element(node, "table", "table-row")
        for value in values:
            attributes = {tag("table", "style-name"): "wrapped"}
            if isinstance(value, bool):
                attributes.update(
                    {
                        tag("office", "value-type"): "boolean",
                        tag("office", "boolean-value"): str(value).lower(),
                    }
                )
            elif isinstance(value, (int, float)):
                attributes.update(
                    {
                        tag("office", "value-type"): "float",
                        tag("office", "value"): str(value),
                    }
                )
            elif value is not None:
                attributes[tag("office", "value-type")] = "string"
            cell = element(row, "table", "table-cell", **attributes)
            if value is not None:
                paragraph(
                    cell, str(value).lower() if isinstance(value, bool) else str(value)
                )


def write_report(inputs: list[Path], output: Path) -> None:
    datasets: list[tuple[str, dict[Metric, str | int | float | bool]]] = []
    for path in inputs:
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise ValueError(f"{path}: expected a JSON object")
        try:
            metrics = reported_metrics(data)
        except (ValueError, TypeError, AttributeError, IndexError) as error:
            raise ValueError(f"{path}: invalid ingestion data: {error}") from error
        datasets.append((f"{data['request']['repository']} ({path})", metrics))
    metrics = sorted({metric for _, values in datasets for metric in values})
    if not metrics:
        raise ValueError("No reported metrics found in the input files")
    labels = {metric: f"{metric.source}: {metric_name(metric)}" for metric in metrics}
    counts = Counter(labels.values())
    labels = {
        metric: label if counts[label] == 1 else f"{label} [{metric.identifier}]"
        for metric, label in labels.items()
    }

    root = ET.Element(
        tag("office", "document-content"), {tag("office", "version"): "1.2"}
    )
    column_styles = element(root, "office", "automatic-styles")
    cell_style = element(
        column_styles,
        "style",
        "style",
        **{tag("style", "name"): "wrapped", tag("style", "family"): "table-cell"},
    )
    element(
        cell_style,
        "style",
        "table-cell-properties",
        **{tag("fo", "wrap-option"): "wrap"},
    )
    for name, width in (
        ("metric-name", 9),
        ("metric-source", 5),
        ("metric-identifier", 20),
        ("metric-range", 4),
        ("metric-description", 15),
        ("tool", 7),
        ("metric", 6),
    ):
        style = element(
            column_styles,
            "style",
            "style",
            **{
                tag("style", "name"): name,
                tag("style", "family"): "table-column",
            },
        )
        element(
            style,
            "style",
            "table-column-properties",
            **{
                tag("style", "column-width"): f"{width}cm",
            },
        )
    body = element(element(root, "office", "body"), "office", "spreadsheet")
    table(
        body,
        "Metric details",
        [
            ["Metric", "Source", "Identifier", "Expected range", "Description"],
            *[
                [
                    labels[m],
                    m.source,
                    m.identifier,
                    m.expected_range,
                    metric_description(m),
                ]
                for m in metrics
            ],
        ],
    )
    table(
        body,
        "Tool comparison",
        [
            ["Tool (input file)", *[labels[m] for m in metrics]],
            *[[name, *[values.get(m) for m in metrics]] for name, values in datasets],
        ],
    )

    styles = ET.Element(
        tag("office", "document-styles"), {tag("office", "version"): "1.2"}
    )
    manifest = ET.Element(
        tag("manifest", "manifest"), {tag("manifest", "version"): "1.2"}
    )
    for path, media in (
        ("/", "application/vnd.oasis.opendocument.spreadsheet"),
        ("content.xml", "text/xml"),
        ("styles.xml", "text/xml"),
    ):
        element(
            manifest,
            "manifest",
            "file-entry",
            **{
                tag("manifest", "full-path"): path,
                tag("manifest", "media-type"): media,
            },
        )
    with ZipFile(output, "w") as archive:
        archive.writestr(
            "mimetype",
            "application/vnd.oasis.opendocument.spreadsheet",
            compress_type=ZIP_STORED,
        )
        for name, tree in (
            ("content.xml", root),
            ("styles.xml", styles),
            ("META-INF/manifest.xml", manifest),
        ):
            archive.writestr(
                name,
                ET.tostring(tree, encoding="utf-8", xml_declaration=True),
                compress_type=ZIP_DEFLATED,
            )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "inputs", nargs="+", type=Path, help="Saved --save-data JSON files"
    )
    parser.add_argument(
        "-o", "--output", required=True, type=Path, help="Output .ods file"
    )
    args = parser.parse_args()
    if args.output.suffix.lower() != ".ods":
        parser.error("output must have an .ods extension")
    if any(args.output.resolve() == path.resolve() for path in args.inputs):
        parser.error("output must not overwrite an input file")
    try:
        write_report(args.inputs, args.output)
    except (OSError, ValueError, json.JSONDecodeError) as error:
        print(f"Error: {error}", file=sys.stderr)
        raise SystemExit(1) from error


if __name__ == "__main__":
    main()
