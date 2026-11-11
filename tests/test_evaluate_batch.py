"""Tests for sequential CSV evaluation."""

import csv
import json
import subprocess
import sys
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "evaluate_batch.py"


def write_csv(path, rows):
    with path.open("w", newline="") as file:
        writer = csv.DictWriter(
            file, fieldnames=["biotoolsID", "name", "homepage", "dois"]
        )
        writer.writeheader()
        writer.writerows(rows)


def row(identifier, url, dois=""):
    return {"biotoolsID": identifier, "name": identifier, "homepage": url, "dois": dois}


def test_batch_and_resume(tmp_path):
    source = tmp_path / "input.csv"
    write_csv(
        source,
        [
            row("one", "https://github.com/a/b", "10.1000/a, 10.1000/b"),
            row("two", "https://gitlab.com/group/subgroup/project"),
            row("skip", "https://github.com/a/b/releases"),
        ],
    )
    executable = tmp_path / "fake"
    executable.write_text(
        "#!" + sys.executable + "\n"
        "import json, pathlib, sys\n"
        "args = sys.argv[1:]\n"
        "path = pathlib.Path(args[args.index('--save-data') + 1])\n"
        "path.write_text(json.dumps(args))\n"
    )
    executable.chmod(0o755)
    output = tmp_path / "out"
    command = [
        sys.executable,
        str(SCRIPT),
        str(source),
        "--output-dir",
        str(output),
        "--executable",
        str(executable),
    ]
    first = subprocess.run(command, capture_output=True, text=True)
    assert first.returncode == 0, first.stderr
    assert "skipped URLs: 1" in first.stdout
    args = json.loads((output / "raw/0002-one.json").read_text())
    assert args[:2] == ["evaluate", "https://github.com/a/b"]
    assert [args[i + 1] for i, x in enumerate(args) if x == "--doi"] == [
        "10.1000/a",
        "10.1000/b",
    ]
    assert "--output" not in args
    assert (output / "raw/0003-two.json").exists()
    assert not (output / "results").exists()
    before = (output / "raw/0002-one.json").read_text()
    again = subprocess.run(command, capture_output=True, text=True)
    assert again.returncode == 0
    assert "skipped existing: 2" in again.stdout
    assert (output / "raw/0002-one.json").read_text() == before


def test_bad_row_and_existing_output_are_reported(tmp_path):
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
    (output / "raw/0002-one.json").write_text("do not overwrite")
    result = subprocess.run(
        [sys.executable, str(SCRIPT), str(source), "--output-dir", str(output)],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 1
    assert "skipped existing: 1" in result.stdout
    assert "row 3" in result.stderr and "row 4" in result.stderr
    assert (output / "raw/0002-one.json").read_text() == "do not overwrite"


def test_dry_run_does_not_create_output(tmp_path):
    source = tmp_path / "input.csv"
    write_csv(source, [row("one", "https://github.com/a/b")])
    output = tmp_path / "out"
    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            str(source),
            "--output-dir",
            str(output),
            "--dry-run",
        ],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert "PLAN row 2 one" in result.stdout
    assert not output.exists()


def test_failed_command_does_not_stop_next_row(tmp_path):
    source = tmp_path / "input.csv"
    write_csv(
        source,
        [row("one", "https://github.com/a/b"), row("two", "https://github.com/a/c")],
    )
    executable = tmp_path / "fake"
    executable.write_text(
        "#!" + sys.executable + "\n"
        "import pathlib, sys\n"
        "pathlib.Path(sys.argv[sys.argv.index('--save-data') + 1]).write_text('{}')\n"
        "sys.exit(4)\n"
    )
    executable.chmod(0o755)
    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            str(source),
            "--output-dir",
            str(tmp_path / "out"),
            "--executable",
            str(executable),
        ],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 1
    assert result.stderr.count("exited with status 4") == 2
    assert list((tmp_path / "out" / "raw").iterdir()) == []


def test_invalid_doi_is_reported_in_dry_run(tmp_path):
    source = tmp_path / "input.csv"
    write_csv(source, [row("one", "https://github.com/a/b", "invalid")])
    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            str(source),
            "--output-dir",
            str(tmp_path / "out"),
            "--dry-run",
        ],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 1
    assert "invalid DOI" in result.stderr
