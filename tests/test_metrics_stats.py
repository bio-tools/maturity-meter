"""Tests for the PDF metrics statistics report."""

import json
import math
import re
import shutil
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from metrics_report import EVERSE, Metric
from metrics_stats import (
    Series,
    classify,
    load_series,
    similarities,
    summary_pages,
    summary_rows,
    summary_value,
)

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "metrics_stats.py"


def test_summary_values_cover_all_metric_types():
    metric = Metric("source", "metric")
    assert summary_value(Series(metric, "numeric", {"a": 0, "b": 4})) == (
        "Median 2; range 0 to 4"
    )
    assert summary_value(Series(metric, "boolean", {"a": True, "b": False})) == (
        "True 1; false 1"
    )
    assert summary_value(Series(metric, "categorical", {"a": "x", "b": "y"})) == (
        "2 distinct; mode x (1)"
    )
    assert summary_value(Series(metric, "excluded", {}, "No results")) == (
        "Excluded: No results"
    )
    grouped = Series(
        metric,
        "publication",
        {"a": '[{"value":"Y"},{"value":"N"}]', "b": '[{"value":"Y"}]'},
    )
    assert summary_value(grouped) == "Publication observations: N 1, Y 2"
    rows = summary_rows([grouped, Series(metric, "excluded", {}, "No results")], 3)
    assert len(rows) == 2
    assert {row[3] for row in rows} == {"2/3\n(66.7%)", "0/3\n(0.0%)"}
    positional = Series(metric, "numeric", {"a": 0}, comparable=False)
    assert "positional, not compared" in summary_rows([positional], 3)[0][4]


def test_summary_paginates_and_includes_every_identifier(tmp_path):
    pytest.importorskip("matplotlib")
    if not shutil.which("pdftotext"):
        pytest.skip("pdftotext unavailable")
    from matplotlib.backends.backend_pdf import PdfPages

    series = [
        Series(Metric("source", f"identifier_{i:03d}"), "numeric", {"a": i})
        for i in range(60)
    ]
    long_identifier = "long_" + "abcdefghij" * 250
    series.append(Series(Metric("source", long_identifier), "numeric", {"a": 0}))
    output = tmp_path / "summary.pdf"
    with PdfPages(output) as pdf:
        summary_pages(pdf, series, 1, datetime(2023, 1, 1, tzinfo=UTC))
    result = subprocess.run(
        ["pdftotext", "-layout", str(output), "-"],
        capture_output=True,
        text=True,
        check=True,
    )
    assert result.stdout.count("Metric summary") > 1
    assert result.stdout.count("Metric / identifier") > 1
    for i in range(60):
        assert result.stdout.count(f"[identifier_{i:03d}]") == 1
    identifier_text = result.stdout.split("[long_", 1)[1].split("]", 1)[0]
    identifier_lines = [
        line.strip()
        for line in identifier_text.splitlines()
        if re.fullmatch(r"[a-j]+", line.strip())
    ]
    assert "long_" + "".join(identifier_lines) == long_identifier


def saved(repo, value=1):
    return {
        "request": {"repository": f"https://github.com/example/{repo}"},
        "repository": {"repo": {"stargazers_count": value}},
        "openalex": {"10.1/test": {"cited_by_count": 4}},
    }


def test_classification_and_grouped_exclusion(tmp_path):
    assert classify(False) == ("boolean", False)
    assert classify("TRUE") == ("boolean", True)
    assert classify(0) == ("numeric", 0)
    assert classify("error") == ("categorical", "error")
    assert classify(float("nan"))[0] == "invalid"
    path = tmp_path / "input.json"
    path.write_text(json.dumps(saved("a")))
    series, count = load_series([path])
    assert count == 1
    grouped = next(s for s in series if s.metric.source == "openalex")
    assert grouped.kind == "excluded"
    assert "grouped" in grouped.reason


def test_compatibility_types_are_boolean_series(tmp_path):
    data = saved("a")
    data["biotools"] = {"function": []}
    data["repository"]["files"] = ["Dockerfile", "setup.py"]
    data["rsec"] = {"files": ["tool.galaxy.json"]}
    path = tmp_path / "input.json"
    path.write_text(json.dumps(data))
    series, _ = load_series([path])
    by_id = {s.metric.identifier: s for s in series}
    for name, value in (
        ("input_formats_present", False),
        ("container_distribution_file", True),
        ("conda_distribution_file", False),
        ("python_distribution_file", True),
        ("rsec_galaxy", True),
    ):
        assert by_id[name].kind == "boolean"
        assert list(by_id[name].values.values()) == [value]


def test_security_file_presence_is_a_boolean_series(tmp_path):
    data = saved("a")
    data["repository"].update(
        {"files": [".github/SECURITY.md"], "files_truncated": True}
    )
    path = tmp_path / "input.json"
    path.write_text(json.dumps(data))
    series, _ = load_series([path])
    by_id = {s.metric.identifier: s for s in series}
    assert by_id["has_security_policy"].kind == "boolean"
    assert list(by_id["has_security_policy"].values.values()) == [True]
    assert "has_gitignore" not in by_id


def test_sustainability_values_use_shared_reference(tmp_path):
    paths = []
    for name in ("a", "b"):
        data = saved(name)
        data["repository"].update(
            {
                "repo": {"pushed_at": "2023-01-08T00:00:00Z"},
                "contributors": [
                    {"name": "a", "contributions": 1},
                    {"name": "b", "contributions": 1},
                ],
                "closed_issues": [
                    {
                        "created_at": "2023-01-01T00:00:00Z",
                        "closed_at": "2023-01-03T00:00:00Z",
                    }
                ],
            }
        )
        path = tmp_path / f"{name}.json"
        path.write_text(json.dumps(data))
        paths.append(path)
    series, _ = load_series(paths, as_of=datetime(2023, 1, 10, tzinfo=UTC))
    by_id = {s.metric.identifier: s for s in series}
    for name, value in (
        ("days_since_last_push", 2),
        ("avg_issue_close_time_days", 2),
        ("inverse_simpson_index", 2),
    ):
        assert by_id[name].kind == "numeric"
        assert list(by_id[name].values.values()) == [value, value]


def test_superlinter_excluded_when_missing_and_charted_when_available(tmp_path):
    data = saved("a")
    path = tmp_path / "input.json"
    path.write_text(json.dumps(data))
    series, _ = load_series([path])
    lint = next(s for s in series if s.metric.source == "SuperLinter")
    assert lint.kind == "excluded"
    assert lint.values == {}
    assert "No SuperLinter results" in lint.reason
    data["quality_checks"] = {
        "checks": [
            {
                "assessesIndicator": {"@id": f"{EVERSE}has_no_linting_issues"},
                "checkingSoftware": {"name": "SuperLinter"},
                "output": "true",
            }
        ]
    }
    path.write_text(json.dumps(data))
    series, _ = load_series([path])
    lint_series = [s for s in series if s.metric.source == "SuperLinter"]
    assert len(lint_series) == 1
    assert lint_series[0].kind == "boolean"
    assert list(lint_series[0].values.values()) == [True]


def test_publication_open_access_charted_without_comparison(tmp_path):
    data = saved("a")
    data["europe_pmc"] = {
        "10.1/a": {"isOpenAccess": "Y"},
        "10.1/b": {"isOpenAccess": "N"},
    }
    path = tmp_path / "input.json"
    path.write_text(json.dumps(data))
    series, _ = load_series([path])
    oa = next(s for s in series if s.metric.identifier == "publication.isOpenAccess")
    assert oa.kind == "publication"
    assert not oa.comparable
    assert {v["value"] for group in oa.values.values() for v in json.loads(group)} == {
        "Y",
        "N",
    }
    assert "Associated publications and open access" in __import__(
        "metrics_stats"
    ).label(oa.metric)


def test_coverage_correlations_do_not_average_grouped_open_access():
    pytest.importorskip("pandas")
    pytest.importorskip("matplotlib")
    from batch_results_plot import _to_number

    group = '[{"value":"Y"},{"value":"N"}]'
    assert math.isnan(_to_number(group, "Associated publications and open access"))


def test_coverage_categories_skip_blanks_and_preserve_shared_metrics():
    pd = pytest.importorskip("pandas")
    pytest.importorskip("matplotlib")
    from batch_results_plot import category_map

    metrics = pd.DataFrame(
        {
            "Metric": ["shared", "other", "unclassified"],
            "Indicator category": ["Fairness, Security", "Other", float("nan")],
        }
    )
    assert category_map(metrics) == {
        "Fairness": ["shared"],
        "Other": ["other"],
        "Security": ["shared"],
    }


def test_incompatible_and_repeated_checks_excluded(tmp_path):
    first = saved("a")
    second = saved("b")
    first["repository"]["repo"]["stargazers_count"] = 1
    second["repository"]["repo"]["stargazers_count"] = "error"
    check = {
        "assessesIndicator": {"@id": "https://example.org/i"},
        "checkingSoftware": {"name": "Checker"},
        "output": "true",
    }
    first["quality_checks"] = {"checks": [check, check]}
    second["quality_checks"] = {"checks": [check]}
    paths = []
    for i, data in enumerate((first, second)):
        path = tmp_path / f"{i}.json"
        path.write_text(json.dumps(data))
        paths.append(path)
    series, _ = load_series(paths)
    assert next(s for s in series if s.metric.source == "Checker").kind == "excluded"
    assert next(s for s in series if s.metric.source == "GitHub").kind == "excluded"


def test_similarity_pairwise_missing_constant_and_minimum():
    def make(name, kind, values):
        return Series(Metric("source", name), kind, values)

    series = [
        make("a", "numeric", {"a": 1, "b": 2, "c": 3, "missing": 100}),
        make("b", "numeric", {"a": 2, "b": 4, "c": 6}),
        make("constant", "numeric", {"a": 1, "b": 1, "c": 1}),
        make("x", "boolean", {"a": True, "b": False, "c": True}),
        make("y", "boolean", {"a": True, "b": True, "c": True}),
    ]
    result = similarities(series, 3)
    assert len(result["numeric"]) == 1
    assert result["numeric"][0][:2] == pytest.approx((1, 3))
    assert result["boolean"][0][:2] == pytest.approx((2 / 3, 3))
    assert not similarities(series, 4)["numeric"]
    assert not similarities(series, 4)["boolean"]


def test_positional_openebench_values_not_compared(tmp_path):
    paths = []
    for i in range(3):
        data = saved(str(i), i)
        data["openebench"] = {"metrics": {"website": {"days": [i]}}}
        path = tmp_path / f"{i}.json"
        path.write_text(json.dumps(data))
        paths.append(path)
    series, _ = load_series(paths)
    positional = next(s for s in series if s.metric.source == "OpenEBench")
    assert positional.kind == "numeric"
    assert not positional.comparable
    assert not similarities(series, 3)["numeric"]


def test_missing_fairchecker_id_warns_and_keeps_other_scores(tmp_path, capsys):
    data = saved("a")
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
    path = tmp_path / "input.json"
    path.write_text(json.dumps(data))
    series, count = load_series([path])
    assert count == 1
    assert any(
        s.metric.source == "FAIRChecker API" and s.metric.identifier == "F1A"
        for s in series
    )
    assert not any(s.metric.identifier == "None" for s in series)
    warning = capsys.readouterr().err
    assert str(path) in warning
    assert "https://example.org/result/missing" in warning


def test_duplicate_tools_rejected_and_shared_repositories_allowed(tmp_path):
    paths = [tmp_path / "a.json", tmp_path / "b.json"]
    for path in paths:
        path.write_text(json.dumps(saved("same")))
    with pytest.raises(ValueError, match="Duplicate tool"):
        load_series(paths)
    for path, identifier in zip(paths, ("first", "second"), strict=True):
        data = saved("same")
        data["request"]["biotools_id"] = identifier
        path.write_text(json.dumps(data))
    assert load_series(paths)[1] == 2


def test_pdf_cli_and_invalid_input(tmp_path):
    pytest.importorskip("matplotlib")
    paths = []
    for i in range(5):
        path = tmp_path / f"{i}.json"
        path.write_text(json.dumps(saved(str(i), i)))
        paths.append(path)
    output = tmp_path / "report.pdf"
    subprocess.run(
        [sys.executable, str(SCRIPT), *(str(p) for p in paths), "-o", str(output)],
        check=True,
    )
    assert output.read_bytes().startswith(b"%PDF-")
    if shutil.which("pdftotext"):
        first_page = subprocess.run(
            ["pdftotext", "-f", "1", "-l", "1", str(output), "-"],
            capture_output=True,
            text=True,
            check=True,
        ).stdout
        assert "Metric summary" in first_page
        assert "[stars]" in first_page
    bad = tmp_path / "bad.json"
    bad.write_text('{"repository": {}}')
    failed = tmp_path / "failed.pdf"
    result = subprocess.run(
        [sys.executable, str(SCRIPT), str(bad), "-o", str(failed)],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 1
    assert "request.repository" in result.stderr
    assert not failed.exists()
