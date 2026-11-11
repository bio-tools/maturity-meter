#!/usr/bin/env python3
"""Create an ODS comparison of reported metrics in saved ingestion data."""

import argparse
import json
import sys
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


def reported_metrics(data: dict[str, Any]) -> dict[Metric, str | int | float | bool]:
    """Extract reported values without calculating or inferring measurements."""
    result: dict[Metric, str | int | float | bool] = {}

    def add(source: str, identifier: str, value: Any, expected_range: str = "") -> None:
        if value is None:
            return
        metric = Metric(source, identifier, expected_range)
        reported = scalar(value)
        if metric in result and result[metric] != reported:
            raise ValueError(f"Conflicting values for {source}: {identifier}")
        result[metric] = reported

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
    for check in quality.get("checks", []):
        indicator = check.get("assessesIndicator", {}).get("@id")
        source = check.get("checkingSoftware", {}).get("name")
        if not indicator or not source:
            raise ValueError("A quality check is missing its indicator ID or source")
        value = check.get("output")
        expected = "true / false" if indicator in BOOLEAN_CHECKS else ""
        add(source, indicator, value, expected)

    # OpenEBench's metrics document is already a source-specific metric record.
    # DOI/year keys preserve the identity of publication and annual observations.
    def openebench(value: Any, path: str) -> None:
        if isinstance(value, dict):
            for key, child in value.items():
                if key.startswith("@") or key in {"doi", "pmid", "title", "year"}:
                    continue
                openebench(child, f"{path}.{key}" if path else key)
        elif isinstance(value, list):
            for index, child in enumerate(value):
                if isinstance(child, dict) and child.get("doi"):
                    label = f"doi={child['doi']}"
                elif isinstance(child, dict) and child.get("year") is not None:
                    label = f"year={child['year']}"
                else:
                    label = str(index)
                openebench(child, f"{path}[{label}]")
        elif value is not None:
            add("OpenEBench", path, value)

    openebench((data.get("openebench") or {}).get("metrics") or {}, "")

    publications = (data.get("biotools") or {}).get("publication") or []
    for publication in publications:
        identifier = publication.get("doi") or publication.get("pmid")
        count = (publication.get("metadata") or {}).get("citationCount")
        if identifier and count is not None:
            add("bio.tools", f"publication[{identifier}].citationCount", count, ">= 0")

    for source, fields in PUBLICATION_FIELDS.items():
        for doi, record in (data.get(source) or {}).items():
            if record is not None:
                for field, expected_range in fields.items():
                    add(
                        source,
                        f"publication[{doi}].{field}",
                        record.get(field),
                        expected_range,
                    )
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
        ["metric-code", "metric-source", "metric-identifier", "metric-range"]
        if name == "Metric details"
        else ["tool", *(["metric"] * (len(rows[0]) - 1))]
    )
    for width in widths:
        element(node, "table", "table-column", **{tag("table", "style-name"): width})
    for values in rows:
        row = element(node, "table", "table-row")
        for value in values:
            attributes = {}
            if isinstance(value, bool):
                attributes = {
                    tag("office", "value-type"): "boolean",
                    tag("office", "boolean-value"): str(value).lower(),
                }
            elif isinstance(value, (int, float)):
                attributes = {
                    tag("office", "value-type"): "float",
                    tag("office", "value"): str(value),
                }
            elif value is not None:
                attributes = {tag("office", "value-type"): "string"}
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
    codes = {metric: f"M{index:03d}" for index, metric in enumerate(metrics, 1)}

    root = ET.Element(
        tag("office", "document-content"), {tag("office", "version"): "1.2"}
    )
    column_styles = element(root, "office", "automatic-styles")
    for name, width in (
        ("metric-code", 2),
        ("metric-source", 5),
        ("metric-identifier", 20),
        ("metric-range", 4),
        ("tool", 7),
        ("metric", 2.5),
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
            ["Column", "Source", "Identifier", "Expected range"],
            *[[codes[m], m.source, m.identifier, m.expected_range] for m in metrics],
        ],
    )
    table(
        body,
        "Tool comparison",
        [
            ["Tool (input file)", *[codes[m] for m in metrics]],
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
