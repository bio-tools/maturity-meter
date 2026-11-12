"""Tests for the PDF metrics statistics report."""

import json
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from metrics_report import Metric
from metrics_stats import Series, classify, load_series, similarities

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "metrics_stats.py"


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
