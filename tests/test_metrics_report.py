"""Tests for the standalone ODS metrics report."""

import json
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from xml.etree import ElementTree as ET
from zipfile import ZIP_STORED, ZipFile

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from metrics_report import (
    EVERSE,
    FAIRNESS_INDICATORS,
    MAINTAINABILITY_INDICATORS,
    SECURITY_INDICATORS,
    SUSTAINABILITY_INDICATORS,
    Metric,
    MetricCategory,
    category_label,
    metric_name,
    reported_metrics,
)

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
            "closed_issues": [
                {
                    "created_at": "2023-01-01T00:00:00Z",
                    "closed_at": "2023-01-02T00:00:00Z",
                }
            ],
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
        "Indicator category",
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
    assert ("GitHub", "avg_issue_close_time_days") in codes
    assert not any("fwci" in row[2] for row in details)


def test_compatibility_presence_and_sources():
    data = saved_data("test", [], {})
    data["biotools"] = {
        "function": [
            {"input": [{"format": [{"term": "BAM"}]}], "output": []},
            {"output": [{"format": [{"uri": "http://example.org/format"}]}]},
        ]
    }
    data["repository"]["files"] = [
        "docker/Dockerfile.dev",
        "recipe/META.YAML",
        "src/PyProject.toml",
    ]
    data["rsec"] = {
        "files": ["test.DEBIAN.YAML", "BIOCONDA_test.YAML", "test.BIOCONTAINERS.YAML"]
    }
    metrics = {
        (metric.source, metric.identifier): value
        for metric, value in reported_metrics(data).items()
        if metric.category == MetricCategory.COMPATIBILITY
    }
    assert metrics == {
        ("bio.tools", "input_formats_present"): True,
        ("bio.tools", "output_formats_present"): True,
        ("Repository files", "container_distribution_file"): True,
        ("Repository files", "conda_distribution_file"): True,
        ("Repository files", "python_distribution_file"): True,
        ("RSEc", "rsec_debian_med"): True,
        ("RSEc", "rsec_bioconda"): True,
        ("RSEc", "rsec_biocontainers"): True,
        ("RSEc", "rsec_galaxy"): False,
    }


def test_compatibility_unknown_empty_and_truncated():
    data = saved_data("test", [], {})
    data.update({"biotools": None, "rsec": None})
    assert not any(
        metric.category == MetricCategory.COMPATIBILITY
        for metric in reported_metrics(data)
    )
    data.update({"biotools": {"function": []}, "rsec": {"files": []}})
    data["repository"].update({"files": [], "files_truncated": False})
    values = {
        metric.identifier: value
        for metric, value in reported_metrics(data).items()
        if metric.category == MetricCategory.COMPATIBILITY
    }
    assert len(values) == 9
    assert not any(values.values())
    data["biotools"] = {}
    data["rsec"] = {}
    data["repository"].update({"files": ["Dockerfile"], "files_truncated": True})
    values = {
        metric.identifier: value
        for metric, value in reported_metrics(data).items()
        if metric.category == MetricCategory.COMPATIBILITY
    }
    assert values == {"container_distribution_file": True}


@pytest.mark.parametrize(
    "source,value",
    [("biotools", {"function": {}}), ("rsec", {"files": {}})],
)
def test_invalid_compatibility_source_rejected(source, value):
    data = saved_data("test", [], {})
    data[source] = value
    with pytest.raises(ValueError):
        reported_metrics(data)


def test_compatibility_columns_in_ods(tmp_path):
    data = saved_data("test", [], {})
    data["biotools"] = {"function": [{"input": [{"format": [{"term": "BAM"}]}]}]}
    data["repository"]["files"] = ["Dockerfile", "setup.py"]
    data["rsec"] = {"files": []}
    source = tmp_path / "input.json"
    source.write_text(json.dumps(data))
    output = tmp_path / "comparison.ods"
    subprocess.run(
        [sys.executable, str(SCRIPT), str(source), "-o", str(output)], check=True
    )
    details, comparison = read_tables(output)
    rows = {row[2]: row for row in details[1:]}
    for identifier, expected in (
        ("input_formats_present", "true"),
        ("output_formats_present", "false"),
        ("container_distribution_file", "true"),
        ("conda_distribution_file", "false"),
        ("python_distribution_file", "true"),
        ("rsec_galaxy", "false"),
    ):
        row = rows[identifier]
        assert row[5] == "Compatibility"
        assert comparison[1][comparison[0].index(row[0])] == expected


def test_fairness_alignment_keeps_sources_and_other_categories():
    for group, identifiers in FAIRNESS_INDICATORS.items():
        for identifier in identifiers:
            metric = Metric("RSFC", identifier)
            assert metric.category == MetricCategory.FAIRNESS
            assert metric_name(metric).startswith(f"{group} — ")
    assert category_label(Metric("RSFC", f"{EVERSE}has_releases")) == (
        "Fairness, Maintainability"
    )
    assert category_label(
        Metric("OpenSSF Scorecard", f"{EVERSE}static_analysis_common_vulnerabilities")
    ) == ("Fairness, Security")
    for source, identifier in (
        ("HowFairIs", f"{EVERSE}software_has_license_for_file_types"),
        ("OpenEBench", "project.build"),
        ("OpenEBench", "deprecated"),
        ("FAIRChecker API", "I3"),
    ):
        assert category_label(Metric(source, identifier)) == "Other"
    assert category_label(Metric("FAIRChecker API", "F2A")) == "Fairness"
    assert "Structured descriptive metadata" in metric_name(
        Metric("FAIRChecker API", "F2A")
    )


def test_maintainability_names_and_non_kept_categories():
    for identifier, name in MAINTAINABILITY_INDICATORS.items():
        metric = Metric("source", identifier)
        assert name in metric_name(metric)
        assert "Maintainability" in category_label(metric)
    for identifier in (
        "files",
        "functions",
        "total_ccn",
        "total_nloc",
        "nloc_per_file",
        f"{EVERSE}project_is_active",
        f"{EVERSE}repository_workflows",
        f"{EVERSE}maintainability_index_ok",
    ):
        assert category_label(Metric("source", identifier)) == "Other"
    assert category_label(Metric("RSFC", f"{EVERSE}has_releases")) == (
        "Fairness, Maintainability"
    )
    assert (
        category_label(Metric("Repository files", "fair_linter_config")) == "Fairness"
    )


def test_scientific_impact_retains_citations_but_not_references():
    for source, identifier in (
        ("GitHub", "stars"),
        ("GitLab", "forks"),
        ("openalex", "publication.fwci"),
        ("openalex", "publication.cited_by_count"),
        ("europe_pmc", "publication.citedByCount"),
        ("bio.tools", "publication.citationCount"),
        ("OpenEBench", "project.publications[].entries[].cit_count"),
        ("OpenEBench", "project.publications[].entries[].citations[].count"),
    ):
        assert category_label(Metric(source, identifier)) == "Scientific Impact"
    assert (
        category_label(
            Metric("OpenEBench", "project.publications[].entries[].ref_count")
        )
        == "Other"
    )


def test_security_categories_and_shared_measurements():
    for identifier, name in SECURITY_INDICATORS.items():
        metric = Metric("source", identifier)
        assert name in metric_name(metric)
        assert "Security" in category_label(metric)
    assert (
        category_label(Metric("OpenSSF Scorecard", f"{EVERSE}dependency_management"))
        == "Security"
    )
    assert (
        category_label(
            Metric(
                "OpenSSF Scorecard", f"{EVERSE}static_analysis_common_vulnerabilities"
            )
        )
        == "Fairness, Security"
    )


def test_security_file_presence_and_unknown():
    data = saved_data("test", [], {})
    assert not any(
        metric.identifier in ("has_security_policy", "has_gitignore")
        for metric in reported_metrics(data)
    )
    data["repository"].update(
        {"files": [".github/SECURITY.md", "sub/.GITIGNORE"], "files_truncated": True}
    )
    values = {m.identifier: v for m, v in reported_metrics(data).items()}
    assert values["has_security_policy"] is True
    assert values["has_gitignore"] is True
    data["repository"]["files"] = [".github/SECURITY.md"]
    values = {m.identifier: v for m, v in reported_metrics(data).items()}
    assert values["has_security_policy"] is True
    assert "has_gitignore" not in values
    data["repository"]["files_truncated"] = False
    values = {m.identifier: v for m, v in reported_metrics(data).items()}
    assert values["has_gitignore"] is False
    data["repository"]["files"] = []
    values = {m.identifier: v for m, v in reported_metrics(data).items()}
    assert values["has_security_policy"] is False
    assert values["has_gitignore"] is False


def test_security_evidence_and_categories_in_ods(tmp_path):
    data = saved_data("test", [], {})
    data["repository"]["files"] = ["SECURITY.md"]
    data["quality_checks"]["checks"] = [
        {
            "assessesIndicator": {"@id": f"{EVERSE}dependency_management"},
            "checkingSoftware": {"name": "OpenSSF Scorecard"},
            "output": "false",
        }
    ]
    source, output = tmp_path / "input.json", tmp_path / "report.ods"
    source.write_text(json.dumps(data))
    subprocess.run(
        [sys.executable, str(SCRIPT), str(source), "-o", str(output)], check=True
    )
    details, comparison = read_tables(output)
    rows = {row[2]: row for row in details[1:]}
    for identifier, category, expected in (
        ("has_security_policy", "Security", "true"),
        ("has_gitignore", "Security", "false"),
        (f"{EVERSE}dependency_management", "Security", "false"),
    ):
        row = rows[identifier]
        assert row[5] == category
        assert comparison[1][comparison[0].index(row[0])] == expected


def test_sustainability_calculations_and_categories():
    data = saved_data("test", [], {})
    data["repository"].update(
        {
            "repo": {"pushed_at": "2023-01-08T00:00:00Z"},
            "closed_issues": [
                {
                    "created_at": "2023-01-01T00:00:00Z",
                    "closed_at": "2023-01-03T00:00:00Z",
                },
                {
                    "created_at": "2023-01-01T00:00:00Z",
                    "closed_at": "2023-01-05T00:00:00Z",
                },
            ],
            "contributors": [
                {"name": "alice", "contributions": 3},
                {"name": "bob", "contributions": 1},
                {"name": "build[bot]", "contributions": 100},
            ],
        }
    )
    as_of = datetime(2023, 1, 10, tzinfo=UTC)
    values = {m.identifier: v for m, v in reported_metrics(data, as_of=as_of).items()}
    assert values["avg_issue_close_time_days"] == 3
    assert values["days_since_last_push"] == 2
    assert values["inverse_simpson_index"] == pytest.approx(1.6)
    for identifier in SUSTAINABILITY_INDICATORS:
        assert "Sustainability" in category_label(Metric("source", identifier))
    assert (
        category_label(Metric("RSFC", f"{EVERSE}software_is_containerized"))
        == "Sustainability"
    )
    assert (
        category_label(Metric("Repository files", "fair_contributing_file"))
        == "Fairness, Sustainability"
    )
    assert (
        category_label(Metric("OpenEBench", "support.issue_tracking.resolve_time"))
        == "Fairness, Sustainability"
    )


def test_sustainability_empty_and_gitlab_activity():
    data = saved_data("test", [], {})
    data["request"]["repository"] = "https://gitlab.com/example/test"
    data["repository"].update(
        {
            "repo": {"last_activity_at": "2023-01-09T12:00:00+00:00"},
            "closed_issues": [],
            "contributors": [{"name": "ci[bot]", "contributions": 3}],
        }
    )
    values = {
        m.identifier: v
        for m, v in reported_metrics(
            data, as_of=datetime(2023, 1, 10, tzinfo=UTC)
        ).items()
    }
    assert values["days_since_last_project_activity"] == 0.5
    assert "avg_issue_close_time_days" not in values
    assert "inverse_simpson_index" not in values
    assert "days_since_last_push" not in values


@pytest.mark.parametrize(
    "update, error",
    [
        (
            {
                "closed_issues": [
                    {"created_at": "invalid", "closed_at": "2023-01-01T00:00:00Z"}
                ]
            },
            "Invalid timestamp",
        ),
        (
            {
                "closed_issues": [
                    {
                        "created_at": "2023-01-02T00:00:00Z",
                        "closed_at": "2023-01-01T00:00:00Z",
                    }
                ]
            },
            "predates",
        ),
        ({"contributors": [{"name": "x", "contributions": -1}]}, "non-negative"),
        ({"repo": {"pushed_at": "2024-01-01T00:00:00Z"}}, "later than"),
    ],
)
def test_invalid_sustainability_inputs_are_reported(update, error):
    data = saved_data("test", [], {})
    data["repository"].update(update)
    with pytest.raises(ValueError, match=error):
        reported_metrics(data, as_of=datetime(2023, 1, 10, tzinfo=UTC))


def test_sustainability_reference_and_values_in_ods(tmp_path):
    data = saved_data("test", [], {})
    data["repository"]["repo"]["pushed_at"] = "2023-01-08T00:00:00Z"
    source, output = tmp_path / "input.json", tmp_path / "report.ods"
    source.write_text(json.dumps(data))
    subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            str(source),
            "-o",
            str(output),
            "--as-of",
            "2023-01-10T00:00:00Z",
        ],
        check=True,
    )
    details, comparison = read_tables(output)
    row = next(r for r in details if r[2] == "days_since_last_push")
    assert "2023-01-10T00:00:00+00:00" in row[4]
    assert row[5] == "Sustainability"
    assert comparison[1][comparison[0].index(row[0])] == "2.0"


def test_scientific_impact_categories_in_ods(tmp_path):
    data = saved_data("test", [], {})
    entry = data["openebench"]["metrics"]["project"]["publications"][0]["entries"][0]
    entry.update({"ref_count": 8, "citations": [{"year": 2024, "count": 2}]})
    data["openalex"]["10.1/test"]["fwci"] = 1.2
    source, output = tmp_path / "input.json", tmp_path / "report.ods"
    source.write_text(json.dumps(data))
    subprocess.run(
        [sys.executable, str(SCRIPT), str(source), "-o", str(output)], check=True
    )
    details, comparison = read_tables(output)
    rows = {row[2]: row for row in details[1:]}
    for identifier in (
        "stars",
        "forks",
        "publication.fwci",
        "publication.cited_by_count",
        "project.publications[].entries[].cit_count",
        "project.publications[].entries[].citations[].count",
    ):
        assert rows[identifier][5] == "Scientific Impact"
    references = rows["project.publications[].entries[].ref_count"]
    assert references[5] == "Other"
    value = comparison[1][comparison[0].index(references[0])]
    assert json.loads(value)[0]["value"] == 8


def test_superlinter_column_blank_or_reported(tmp_path):
    first = saved_data("first", [], {"avg_ccn": 2})
    second = saved_data("second", [], {"avg_ccn": 3})
    second["quality_checks"]["checks"] = [
        {
            "assessesIndicator": {"@id": f"{EVERSE}has_no_linting_issues"},
            "checkingSoftware": {"name": "SuperLinter"},
            "output": "false",
        }
    ]
    paths = [tmp_path / "first.json", tmp_path / "second.json"]
    for path, data in zip(paths, (first, second), strict=True):
        path.write_text(json.dumps(data))
    for inputs, expected in ((paths[:1], [""]), (paths, ["", "false"])):
        output = tmp_path / f"report-{len(inputs)}.ods"
        subprocess.run(
            [sys.executable, str(SCRIPT), *(str(p) for p in inputs), "-o", str(output)],
            check=True,
        )
        details, comparison = read_tables(output)
        rows = [r for r in details[1:] if r[1] == "SuperLinter"]
        assert len(rows) == 1
        assert rows[0][2] == f"{EVERSE}has_no_linting_issues"
        assert "No linting issues" in rows[0][0]
        assert rows[0][5] == "Fairness, Maintainability"
        column = comparison[0].index(rows[0][0])
        assert [row[column] for row in comparison[1:]] == expected


def test_fairness_presence_preserves_missing_and_truncation():
    data = saved_data("test", [], {})
    data["repository"].update(
        {"files": ["docs/readme.md", "CITATION.cff"], "files_truncated": True}
    )
    data["biotools"] = {
        "description": "test",
        "publication": [],
        "credit": [{"name": "Author"}],
        "documentation": [{"type": ["Installation instructions"]}],
        "download": [{"type": "Source code"}],
        "function": [{"operation": [{"term": "analysis"}]}],
    }
    data["rsec"] = {"files": []}
    metrics = {(m.source, m.identifier): v for m, v in reported_metrics(data).items()}
    assert metrics["Repository files", "fair_citation_file"] is True
    assert metrics["Repository files", "fair_docs_directory"] is True
    assert ("Repository files", "fair_governance_file") not in metrics
    assert metrics["bio.tools", "fair_biotools_publications"] is False
    assert metrics["bio.tools", "fair_biotools_credits"] is True
    assert metrics["bio.tools", "fair_biotools_installation_docs"] is True
    assert metrics["bio.tools", "fair_biotools_source_download"] is True
    assert metrics["bio.tools", "fair_biotools_binary_download"] is False
    assert metrics["bio.tools", "fair_biotools_operations"] is True
    assert metrics["RSEc", "fair_rsec_registry"] is True
    assert ("Repository", "fair_release_assets") not in metrics
    assert ("Repository", "fair_repository_public") not in metrics
    data["repository"]["files_truncated"] = False
    data["repository"]["repo"]["private"] = False
    data["repository"]["latest_release"] = {"assets": {"links": []}}
    data["biotools"] = None
    data["rsec"] = None
    metrics = {(m.source, m.identifier): v for m, v in reported_metrics(data).items()}
    assert metrics["Repository files", "fair_governance_file"] is False
    assert metrics["Repository", "fair_repository_public"] is True
    assert metrics["Repository", "fair_release_assets"] is False
    assert ("bio.tools", "fair_biotools_publications") not in metrics
    assert ("RSEc", "fair_rsec_registry") not in metrics


def test_fairness_group_and_category_in_ods(tmp_path):
    data = saved_data("test", [], {})
    data["repository"]["files"] = ["CITATION.cff"]
    data["quality_checks"]["checks"] = [
        {
            "assessesIndicator": {"@id": f"{EVERSE}has_releases"},
            "checkingSoftware": {"name": "RSFC"},
            "output": "true",
        },
        {
            "assessesIndicator": {
                "@id": f"{EVERSE}software_has_license_for_file_types"
            },
            "checkingSoftware": {"name": "HowFairIs"},
            "output": "false",
        },
    ]
    source, output = tmp_path / "input.json", tmp_path / "report.ods"
    source.write_text(json.dumps(data))
    subprocess.run(
        [sys.executable, str(SCRIPT), str(source), "-o", str(output)], check=True
    )
    details, comparison = read_tables(output)
    rows = {row[2]: row for row in details[1:]}
    row = rows[f"{EVERSE}has_releases"]
    assert "Releases and versioning conventions" in row[0]
    assert row[5] == "Fairness, Maintainability"
    assert comparison[1][comparison[0].index(row[0])] == "true"
    assert rows[f"{EVERSE}software_has_license_for_file_types"][5] == "Other"
    assert "Software citation information" in rows["fair_citation_file"][0]


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


def test_direct_fairchecker_scores_and_legacy_results_are_distinct(tmp_path):
    source = tmp_path / "input.json"
    data = saved_data("test", [check("false")], {})
    data["quality_checks"]["checks"][0].update(
        {
            "assessesIndicator": {"@id": "https://w3id.org/fair/principles/terms/F1A"},
            "checkingSoftware": {"name": "FAIRChecker"},
        }
    )
    data["fair_checker"] = [
        {
            "@type": ["https://w3id.org/ftr#TestResult"],
            "https://w3id.org/ftr#outputFromTest": [
                {"@id": "https://fair-checker.example/test/F1A"}
            ],
            "http://www.w3.org/ns/prov#value": [{"@value": 0}],
        }
    ]
    source.write_text(json.dumps(data))
    output = tmp_path / "comparison.ods"
    subprocess.run(
        [sys.executable, str(SCRIPT), str(source), "-o", str(output)], check=True
    )
    details, comparison = read_tables(output)
    labels = {(row[1], row[2]): row[0] for row in details[1:]}
    direct = labels["FAIRChecker API", "F1A"]
    legacy = labels["FAIRChecker", "https://w3id.org/fair/principles/terms/F1A"]
    assert comparison[1][comparison[0].index(direct)] == "0"
    assert comparison[1][comparison[0].index(legacy)] == "false"


def test_missing_fairchecker_id_warns_and_preserves_valid_results(tmp_path):
    source = tmp_path / "input.json"
    data = saved_data("test", [], {"files": 4})
    data["fair_checker"] = [
        {
            "@id": "https://example.org/result/missing",
            "@type": ["https://w3id.org/ftr#TestResult"],
            "https://w3id.org/ftr#outputFromTest": [
                {"@id": f"https://fair-checker.example/test/{identifier}"}
            ],
            "http://www.w3.org/ns/prov#value": [{"@value": value}],
        }
        for identifier, value in (("None", 2), ("F1A", 0))
    ]
    source.write_text(json.dumps(data))
    output = tmp_path / "comparison.ods"
    result = subprocess.run(
        [sys.executable, str(SCRIPT), str(source), "-o", str(output)],
        check=True,
        capture_output=True,
        text=True,
    )
    assert str(source) in result.stderr
    assert "https://example.org/result/missing" in result.stderr
    assert "no usable test ID" in result.stderr
    details, comparison = read_tables(output)
    labels = {(row[1], row[2]): row[0] for row in details[1:]}
    assert ("FAIRChecker API", "None") not in labels
    assert comparison[1][comparison[0].index(labels["FAIRChecker API", "F1A"])] == "0"
    assert comparison[1][comparison[0].index(labels["Lizard", "files"])] == "4"


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
