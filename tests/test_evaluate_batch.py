"""Tests for batch evaluation from a bio.tools CSV."""

import csv
import json

import pytest
from typer.testing import CliRunner

from maturity_meter.adapters.cli.app import app
from maturity_meter.config import Settings
from maturity_meter.models import EvaluationRequest, IngestedData
from maturity_meter.services import batch


def write_csv(path, rows):
    with path.open("w", newline="") as file:
        writer = csv.DictWriter(
            file, fieldnames=["biotoolsID", "name", "homepage", "dois"]
        )
        writer.writeheader()
        writer.writerows(rows)


def row(identifier, url, dois=""):
    return {"biotoolsID": identifier, "name": identifier, "homepage": url, "dois": dois}


@pytest.fixture
def requests(monkeypatch):
    """Record the requests evaluated instead of fetching anything."""
    seen = []

    async def fake_ingest(request):
        seen.append(request)
        return IngestedData(request=request, repository={})

    monkeypatch.setattr(batch, "ingest", fake_ingest)
    # No token: the batch then never checks GitHub's rate limit.
    monkeypatch.setattr(batch, "get_settings", lambda: Settings(_env_file=None))
    return seen


def run_batch(source, output, *extra):
    return CliRunner().invoke(
        app, ["batch", str(source), "--output-dir", str(output), *extra]
    )


def test_batch_and_resume(tmp_path, requests):
    source = tmp_path / "input.csv"
    write_csv(
        source,
        [
            row("one", "https://github.com/a/b", "10.1000/a, 10.1000/b"),
            row("two", "https://gitlab.com/group/subgroup/project"),
            row("skip", "https://github.com/a/b/releases"),
        ],
    )
    output = tmp_path / "out"
    first = run_batch(source, output)
    assert first.exit_code == 0, first.output
    assert "skipped URLs: 1" in first.stdout
    assert [request.repository for request in requests] == [
        "https://github.com/a/b",
        "https://gitlab.com/group/subgroup/project",
    ]
    assert requests[0].dois == ["10.1000/a", "10.1000/b"]
    assert requests[0].biotools_id == "one"
    saved = json.loads((output / "raw/one.json").read_text())
    assert saved["request"]["repository"] == "https://github.com/a/b"
    assert (output / "raw/two.json").exists()
    assert (output / "logs/one.log").exists()
    assert sorted(path.name for path in (output / "raw").iterdir()) == [
        "one.json",
        "two.json",
    ]
    result = json.loads((output / "results/one.json").read_text())
    assert set(result["maturity"]) >= {"fairness", "security"}
    assert (output / "results/two.json").exists()
    before = (output / "raw/one.json").read_text()
    again = run_batch(source, output)
    assert again.exit_code == 0
    # Saved data is scored again without fetching anything.
    assert "from saved data: 2" in again.stdout
    assert "SCORED row 2 one" in again.stdout
    assert len(requests) == 2
    assert (output / "raw/one.json").read_text() == before


def test_bad_row_and_existing_output_are_reported(tmp_path, requests):
    source = tmp_path / "input.csv"
    write_csv(
        source,
        [
            row("one", "https://github.com/a/b"),
            row("bad", "https://github.com/a"),
            row("site", "https://example.github.com/"),
        ],
    )
    output = tmp_path / "out"
    (output / "raw").mkdir(parents=True)
    saved = IngestedData(
        request=EvaluationRequest(repository="https://github.com/a/b"),
        repository={"repo": {"stargazers_count": 7}},
    )
    saved.save(output / "raw/0002-one.json")
    before = (output / "raw/0002-one.json").read_text()
    result = run_batch(source, output)
    assert result.exit_code == 1
    assert "from saved data: 1" in result.stdout
    assert "row 3" in result.stderr and "row 4" in result.stderr
    assert (output / "raw/0002-one.json").read_text() == before
    assert (output / "results/one.json").exists()
    assert requests == []


def test_dry_run_does_not_create_output(tmp_path, requests):
    source = tmp_path / "input.csv"
    write_csv(source, [row("one", "https://github.com/a/b")])
    output = tmp_path / "out"
    result = run_batch(source, output, "--dry-run")
    assert result.exit_code == 0
    assert "PLAN row 2 one: fetch: https://github.com/a/b" in result.stdout
    assert not output.exists()
    assert requests == []


def test_failed_evaluation_does_not_stop_next_row(tmp_path, monkeypatch, requests):
    async def failing_ingest(request):
        requests.append(request)
        raise RuntimeError("evaluation broke")

    monkeypatch.setattr(batch, "ingest", failing_ingest)
    source = tmp_path / "input.csv"
    write_csv(
        source,
        [row("one", "https://github.com/a/b"), row("two", "https://github.com/a/c")],
    )
    output = tmp_path / "out"
    result = run_batch(source, output)
    assert result.exit_code == 1
    assert result.stderr.count("evaluation broke") == 2
    assert len(requests) == 2
    assert list((output / "raw").iterdir()) == []
    assert list((output / "results").iterdir()) == []
    log = (output / "logs/one.log").read_text()
    assert "RuntimeError: evaluation broke" in log


def test_invalid_doi_is_reported_in_dry_run(tmp_path, requests):
    source = tmp_path / "input.csv"
    write_csv(source, [row("one", "https://github.com/a/b", "invalid")])
    result = run_batch(source, tmp_path / "out", "--dry-run")
    assert result.exit_code == 1
    assert "invalid DOI" in result.stderr


def test_fill_missing_fetches_only_what_saved_data_lacks(tmp_path, requests):
    source = tmp_path / "input.csv"
    write_csv(source, [row("one", "https://github.com/a/b")])
    output = tmp_path / "out"
    (output / "raw").mkdir(parents=True)
    saved = IngestedData(
        request=EvaluationRequest(repository="https://github.com/a/b"),
        repository={"repo": {"stargazers_count": 7}},
    )
    saved.save(output / "raw/0002-one.json")
    result = run_batch(source, output, "--fill-missing")
    assert result.exit_code == 0, result.output
    assert "fetched: 1" in result.stdout
    # The saved sources are passed on, so only missing ones would be fetched.
    assert requests[0].data.repository == {"repo": {"stargazers_count": 7}}
    assert (output / "results/one.json").exists()


def test_duplicate_csv_ids_are_reported_without_second_evaluation(tmp_path, requests):
    source = tmp_path / "input.csv"
    write_csv(
        source,
        [row("one", "https://github.com/a/b"), row("ONE", "https://github.com/a/c")],
    )
    output = tmp_path / "out"
    result = run_batch(source, output)
    assert result.exit_code == 1
    assert "duplicate bio.tools ID" in result.output
    assert len(requests) == 1
    assert (output / "raw/one.json").exists()


def test_multiple_saved_files_reported_without_overwrite(tmp_path, requests):
    source = tmp_path / "input.csv"
    write_csv(source, [row("one", "https://github.com/a/b")])
    output = tmp_path / "out"
    (output / "raw").mkdir(parents=True)
    saved = IngestedData(
        request=EvaluationRequest(
            repository="https://github.com/a/b", biotools_id="one"
        ),
        repository={},
    )
    saved.save(output / "raw/one.json")
    saved.save(output / "raw/0032-one.json")
    result = run_batch(source, output)
    assert result.exit_code == 1
    assert "multiple saved data files" in result.output
    assert not (output / "results").exists()
    assert requests == []


def test_legacy_file_with_mismatched_id_is_not_scored(tmp_path, requests):
    source = tmp_path / "input.csv"
    write_csv(source, [row("one", "https://github.com/a/b")])
    output = tmp_path / "out"
    (output / "raw").mkdir(parents=True)
    saved = IngestedData(
        request=EvaluationRequest(
            repository="https://github.com/a/b", biotools_id="other"
        ),
        repository={},
    )
    saved.save(output / "raw/0123-one.json")
    result = run_batch(source, output)
    assert result.exit_code == 1
    assert "does not match" in result.output
    assert not (output / "results/one.json").exists()
    assert requests == []


def test_number_prefix_in_id_does_not_conflict_with_other_tool(tmp_path, requests):
    source = tmp_path / "input.csv"
    write_csv(source, [row("one", "https://github.com/a/b")])
    output = tmp_path / "out"
    (output / "raw").mkdir(parents=True)
    for identifier in ("one", "123-one"):
        data = IngestedData(
            request=EvaluationRequest(
                repository="https://github.com/a/b", biotools_id=identifier
            ),
            repository={},
        )
        data.save(output / f"raw/{identifier}.json")
    result = run_batch(source, output)
    assert result.exit_code == 0, result.output
    assert "from saved data: 1" in result.output
    assert requests == []
