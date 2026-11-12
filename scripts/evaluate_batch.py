#!/usr/bin/env python3
"""Evaluate tools listed in a bio.tools CSV, one at a time."""

import argparse
import csv
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path
from urllib.parse import urlsplit


class SkippedURL(ValueError):
    """A URL points inside a repository instead of to its root."""


def repository_url(url: str) -> str:
    """Accept repository URLs, not GitHub pages within a repository."""
    parsed = urlsplit(url.strip())
    host = (parsed.hostname or "").lower().removeprefix("www.")
    parts = parsed.path.strip("/").split("/")
    if (
        parsed.scheme not in {"http", "https"}
        or host not in {"github.com", "gitlab.com"}
        or parsed.username
        or parsed.password
        or parsed.port
        or parsed.query
        or parsed.fragment
        or any(not part for part in parts)
        or len(parts) < 2
    ):
        raise ValueError(f"not a GitHub or GitLab repository URL: {url!r}")
    if host == "github.com" and len(parts) != 2:
        raise SkippedURL(f"GitHub URL has a path beyond the repository: {url!r}")
    if host == "gitlab.com" and "-" in parts:
        raise SkippedURL(f"GitLab URL points inside a repository: {url!r}")
    return url.strip()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "csv_file", type=Path, help="CSV with biotoolsID, homepage and dois"
    )
    parser.add_argument(
        "--output-dir",
        required=True,
        type=Path,
        help="Directory containing the raw data JSON files",
    )
    parser.add_argument(
        "--executable",
        default="maturity-meter",
        help="Path to the maturity-meter executable (default: maturity-meter on PATH)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate and list rows without evaluating",
    )
    args = parser.parse_args()
    succeeded = skipped = skipped_urls = failed = 0
    try:
        with args.csv_file.open(encoding="utf-8-sig", newline="") as file:
            reader = csv.DictReader(file)
            required = {"biotoolsID", "homepage", "dois"}
            if not reader.fieldnames or not required.issubset(reader.fieldnames):
                raise ValueError(
                    f"CSV must contain columns: {', '.join(sorted(required))}"
                )
            if not args.dry_run:
                (args.output_dir / "raw").mkdir(parents=True, exist_ok=True)
            for row_number, row in enumerate(reader, 2):
                label = f"row {row_number}"
                try:
                    biotools_id = (row.get("biotoolsID") or "").strip()
                    if not re.fullmatch(r"[A-Za-z0-9_.-]+", biotools_id):
                        raise ValueError(f"invalid bio.tools ID: {biotools_id!r}")
                    repository = repository_url(row.get("homepage") or "")
                    dois = [doi.strip() for doi in (row.get("dois") or "").split(",")]
                    dois = [doi for doi in dois if doi]
                    for doi in dois:
                        bare = re.sub(
                            r"^(?:https?://(?:dx\.)?doi\.org/|doi:)",
                            "",
                            doi,
                            flags=re.IGNORECASE,
                        )
                        if not re.fullmatch(r"10\.\d{4,9}/\S+", bare):
                            raise ValueError(f"invalid DOI: {doi!r}")
                    stem = f"{row_number:04d}-{biotools_id}"
                    raw = args.output_dir / "raw" / f"{stem}.json"
                    if raw.exists():
                        print(f"SKIP {label} {biotools_id}: data file already exists")
                        skipped += 1
                        continue
                    action = "PLAN" if args.dry_run else "RUN"
                    print(f"{action} {label} {biotools_id}: {repository}", flush=True)
                    if not args.dry_run:
                        with tempfile.TemporaryDirectory(dir=raw.parent) as directory:
                            temporary_raw = Path(directory) / "data.json"
                            command = [
                                args.executable,
                                "evaluate",
                                repository,
                                "--biotools-id",
                                biotools_id,
                                "--save-data",
                                str(temporary_raw),
                            ]
                            for doi in dois:
                                command.extend(["--doi", doi])
                            completed = subprocess.run(
                                command, stdout=subprocess.DEVNULL, check=False
                            )
                            if completed.returncode:
                                raise ValueError(
                                    "maturity-meter exited with status "
                                    f"{completed.returncode}"
                                )
                            if not temporary_raw.is_file():
                                raise ValueError(
                                    "maturity-meter did not create data file"
                                )
                            try:
                                os.link(temporary_raw, raw)
                            except FileExistsError as error:
                                raise ValueError(
                                    f"data file appeared during evaluation: {raw}"
                                ) from error
                    succeeded += 1
                except SkippedURL as error:
                    print(f"SKIP {label}: {error}", file=sys.stderr, flush=True)
                    skipped_urls += 1
                except ValueError as error:
                    print(f"ERROR {label}: {error}", file=sys.stderr, flush=True)
                    failed += 1
    except (OSError, csv.Error, ValueError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1
    action = "Planned" if args.dry_run else "Completed"
    print(
        f"{action}: {succeeded}; skipped existing: {skipped}; "
        f"skipped URLs: {skipped_urls}; errors: {failed}"
    )
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
