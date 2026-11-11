"""Tests for the standalone ODS metrics report."""

import json
import subprocess
import sys
from pathlib import Path
from xml.etree import ElementTree as ET
from zipfile import ZIP_STORED, ZipFile

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "metrics_report.py"
NS = {
    "table": "urn:oasis:names:tc:opendocument:xmlns:table:1.0",
    "text": "urn:oasis:names:tc:opendocument:xmlns:text:1.0",
}


def saved_data(repo, checks, code_metrics):
    return {
        "request": {"repository": f"https://github.com/example/{repo}"},
        "repository": {
            "repo": {"stargazers_count": 0, "forks_count": 2},
            "default_branch_protected": False,
            "open_issues": 0,
            "closed_issues": [{"created_at": "2023-01-01", "closed_at": "2023-01-02"}],
        },
        "code_metrics": code_metrics,
        "quality_checks": {"checks": checks},
        "openebench": {
            "metrics": {
                "project": {
                    "publications": [
                        {"entries": [{"doi": "10.1/test", "cit_count": 3}]}
                    ]
                }
            }
        },
        "openalex": {"10.1/test": {"cited_by_count": 5, "fwci": None}},
    }


def check(output):
    return {
        "assessesIndicator": {"@id": "https://example.org/indicator"},
        "checkingSoftware": {"name": "Example tool"},
        "output": output,
    }


def read_tables(path):
    with ZipFile(path) as archive:
        assert archive.infolist()[0].filename == "mimetype"
        assert archive.infolist()[0].compress_type == ZIP_STORED
        assert (
            archive.read("mimetype")
            == b"application/vnd.oasis.opendocument.spreadsheet"
        )
        ET.fromstring(archive.read("styles.xml"))
        ET.fromstring(archive.read("META-INF/manifest.xml"))
        root = ET.fromstring(archive.read("content.xml"))
    return [
        [
            ["".join(cell.itertext()) for cell in row.findall("table:table-cell", NS)]
            for row in table.findall("table:table-row", NS)
        ]
        for table in root.findall(".//table:table", NS)
    ]


def test_report_preserves_reported_values_and_aligns_sources(tmp_path):
    first = tmp_path / "first.json"
    second = tmp_path / "second.json"
    first.write_text(
        json.dumps(saved_data("first", [check("false")], {"avg_ccn": 3.41}))
    )
    second.write_text(
        json.dumps(saved_data("second", [check("error")], {"avg_ccn": None}))
    )
    output = tmp_path / "comparison.ods"

    subprocess.run(
        [sys.executable, str(SCRIPT), str(first), str(second), "-o", str(output)],
        check=True,
    )

    details, comparison = read_tables(output)
    assert details[0] == [
        "Metric",
        "Source",
        "Identifier",
        "Expected range",
        "Description",
    ]
    codes = {(row[1], row[2]): row[0] for row in details[1:]}
    assert all(row[4] for row in details[1:])
    assert len(details) - 1 == len(comparison[0]) - 1
    score = comparison[0].index(codes["Example tool", "https://example.org/indicator"])
    avg = comparison[0].index(codes["Lizard", "avg_ccn"])
    stars = comparison[0].index(codes["GitHub", "stars"])
    assert [row[score] for row in comparison[1:]] == ["false", "error"]
    assert [row[avg] for row in comparison[1:]] == ["3.41", ""]
    assert [row[stars] for row in comparison[1:]] == ["0", "0"]
    assert ("OpenEBench", "project.publications[].entries[].cit_count") in codes
    assert ("openalex", "publication.cited_by_count") in codes
    assert not any("close_time" in row[2] for row in details)
    assert not any("fwci" in row[2] for row in details)


def test_multiple_checks_for_one_indicator_are_preserved(tmp_path):
    source = tmp_path / "input.json"
    first = check("true")
    first.update({"process": "First test", "evidence": "First evidence"})
    second = check("false")
    second.update({"process": "Second test", "evidence": "Second evidence"})
    source.write_text(json.dumps(saved_data("test", [first, second], {})))
    output = tmp_path / "comparison.ods"
    subprocess.run(
        [sys.executable, str(SCRIPT), str(source), "-o", str(output)], check=True
    )
    details, comparison = read_tables(output)
    label = next(
        row[0]
        for row in details
        if row[1:3] == ["Example tool", "https://example.org/indicator"]
    )
    cell = comparison[1][comparison[0].index(label)]
    checks = json.loads(cell)
    assert [(item["output"], item["process"]) for item in checks] == [
        ("true", "First test"),
        ("false", "Second test"),
    ]
    assert checks[1]["evidence"] == "Second evidence"


def test_publications_share_columns_and_retain_values(tmp_path):
    first = saved_data("first", [], {})
    second = saved_data("second", [], {})
    first["openalex"] = {
        "10.1/a": {"cited_by_count": 5, "fwci": 0.9},
        "10.1/b": {"cited_by_count": 9, "fwci": 1.4},
    }
    second["openalex"] = {"10.1/c": {"cited_by_count": 2, "fwci": 1.1}}
    first["biotools"] = {
        "publication": [
            {"doi": "10.1/a", "metadata": {"citationCount": 4}},
            {"pmid": "123", "metadata": {"citationCount": 7}},
        ]
    }
    second["biotools"] = {
        "publication": [{"doi": "10.1/c", "metadata": {"citationCount": 8}}]
    }
    first["europe_pmc"] = {
        "10.1/a": {"citedByCount": 1},
        "10.1/b": {"citedByCount": 3},
    }
    first["openebench"]["metrics"]["project"]["publications"][0]["entries"] = [
        {"doi": "10.1/a", "cit_count": 3, "citations": [{"year": 2024, "count": 2}]},
        {"doi": "10.1/b", "cit_count": 6, "citations": [{"year": 2025, "count": 4}]},
    ]
    files = []
    for index, data in enumerate((first, second)):
        path = tmp_path / f"{index}.json"
        path.write_text(json.dumps(data))
        files.append(path)
    output = tmp_path / "report.ods"
    subprocess.run(
        [sys.executable, str(SCRIPT), *(str(p) for p in files), "-o", str(output)],
        check=True,
    )
    details, comparison = read_tables(output)
    codes = {(row[1], row[2]): row[0] for row in details[1:]}
    assert len(comparison[0]) == len(set(comparison[0]))
    for source, identifier, expected in (
        ("openalex", "publication.cited_by_count", [("10.1/a", 5), ("10.1/b", 9)]),
        ("bio.tools", "publication.citationCount", [("10.1/a", 4), ("123", 7)]),
        ("europe_pmc", "publication.citedByCount", [("10.1/a", 1), ("10.1/b", 3)]),
        (
            "OpenEBench",
            "project.publications[].entries[].cit_count",
            [("10.1/a", 3), ("10.1/b", 6)],
        ),
    ):
        cell = comparison[1][comparison[0].index(codes[source, identifier])]
        values = json.loads(cell)
        assert [(v.get("doi") or v.get("pmid"), v["value"]) for v in values] == expected
    annual = json.loads(
        comparison[1][
            comparison[0].index(
                codes[
                    "OpenEBench", "project.publications[].entries[].citations[].count"
                ]
            )
        ]
    )
    assert [(v["doi"], v["year"], v["value"]) for v in annual] == [
        ("10.1/a", 2024, 2),
        ("10.1/b", 2025, 4),
    ]
    openalex_column = comparison[0].index(
        codes["openalex", "publication.cited_by_count"]
    )
    assert json.loads(comparison[2][openalex_column]) == [{"doi": "10.1/c", "value": 2}]


def test_bad_input_reports_error_without_creating_output(tmp_path):
    bad = tmp_path / "bad.json"
    bad.write_text('{"repository": {}}')
    output = tmp_path / "comparison.ods"
    result = subprocess.run(
        [sys.executable, str(SCRIPT), str(bad), "-o", str(output)],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 1
    assert "request.repository" in result.stderr
    assert not output.exists()


def test_many_columns_are_supported(tmp_path):
    source = tmp_path / "input.json"
    data = saved_data("large", [], {f"metric_{i}": i for i in range(117)})
    source.write_text(json.dumps(data))
    output = tmp_path / "comparison.ods"
    result = subprocess.run(
        [sys.executable, str(SCRIPT), str(source), "-o", str(output)],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    details, comparison = read_tables(output)
    assert len(details) > 117
    assert len(comparison[0]) == len(details)


def test_spreadsheet_preserves_cell_types(tmp_path):
    source = tmp_path / "input.json"
    source.write_text(
        json.dumps(saved_data("test", [check("false")], {"avg_ccn": 3.41}))
    )
    output = tmp_path / "comparison.ods"
    subprocess.run(
        [sys.executable, str(SCRIPT), str(source), "-o", str(output)], check=True
    )
    with ZipFile(output) as archive:
        root = ET.fromstring(archive.read("content.xml"))
    office = "{urn:oasis:names:tc:opendocument:xmlns:office:1.0}"
    tables = root.findall(".//table:table", NS)
    rows = tables[1].findall("table:table-row", NS)
    headings = ["".join(c.itertext()) for c in rows[0].findall("table:table-cell", NS)]
    cells = rows[1].findall("table:table-cell", NS)
    details = read_tables(output)[0]
    codes = {(row[1], row[2]): row[0] for row in details[1:]}
    avg = cells[headings.index(codes["Lizard", "avg_ccn"])]
    assert avg.get(office + "value-type") == "float"
    assert avg.get(office + "value") == "3.41"
    protection = cells[headings.index(codes["GitHub", "default_branch_protected"])]
    assert protection.get(office + "value-type") == "boolean"
    assert protection.get(office + "boolean-value") == "false"
    check_cell = cells[
        headings.index(codes["Example tool", "https://example.org/indicator"])
    ]
    assert check_cell.get(office + "value-type") == "string"
