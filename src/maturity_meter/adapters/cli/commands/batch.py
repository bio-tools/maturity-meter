"""Batch evaluation command for the Typer CLI adapter.

The command reads a bio.tools CSV export, delegates the evaluations to the batch
service and prints one line per event as it happens.
"""

import asyncio
import csv
from pathlib import Path
from typing import Annotated

import typer

from maturity_meter.services.batch import (
    BatchEvent,
    BatchSummary,
    evaluate_batch,
    read_csv,
)


def format_event(event: BatchEvent) -> tuple[str, bool]:
    """Return the terminal line for ``event`` and whether it is an error.

    Parameters
    ----------
    event : BatchEvent
        Event reported by the batch service.

    Returns
    -------
    tuple of (str, bool)
        The line, and True if it belongs on stderr.
    """
    label = f"row {event.row} {event.biotools_id}".rstrip()
    match event.kind:
        case "invalid":
            return f"ERROR {label}: {event.message}", True
        case "skip_url":
            return f"SKIP {label}: {event.message}", True
        case "skip_existing":
            return f"SKIP {label}: data file already exists", False
        case "plan":
            return f"PLAN {label}: {event.message}", False
        case "start":
            return f"RUN {label}: {event.message}", False
        case "done":
            return f"DONE {label} in {event.seconds or 0:.0f}s", False
        case "failed":
            return f"ERROR {label}: {event.message}", True
        case "wait":
            minutes = (event.seconds or 0) / 60
            return f"WAIT {event.message}; waiting {minutes:.0f} min", False


def _report(event: BatchEvent) -> None:
    line, error = format_event(event)
    typer.echo(line, err=error)


def _summary_line(summary: BatchSummary, dry_run: bool) -> str:
    action = "Planned" if dry_run else "Completed"
    return (
        f"{action}: {summary.succeeded}; skipped existing: "
        f"{summary.skipped_existing}; skipped URLs: {summary.skipped_urls}; "
        f"errors: {summary.failed}"
    )


def command(
    csv_file: Annotated[
        Path,
        typer.Argument(
            exists=True,
            dir_okay=False,
            help="bio.tools CSV with biotoolsID, homepage and dois columns.",
        ),
    ],
    output_dir: Annotated[
        Path,
        typer.Option(
            "--output-dir",
            "-o",
            file_okay=False,
            help=(
                "Directory for the data (raw/) and log (logs/) files. Tools that "
                "already have a data file there are skipped."
            ),
        ),
    ],
    jobs: Annotated[
        int | None,
        typer.Option(
            "--jobs",
            "-j",
            min=1,
            show_default=False,
            help=(
                "Number of tools in progress at the same time (default: "
                "MATURITY_METER_BATCH_JOBS, or 4). Their resqui checks share one "
                "limit, MATURITY_METER_RESQUI_PARALLEL."
            ),
        ),
    ] = None,
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", help="Validate and list rows without evaluating."),
    ] = False,
) -> None:
    """Evaluate every tool in a bio.tools CSV and save their data."""
    try:
        rows = read_csv(csv_file)
    except (OSError, csv.Error, ValueError) as error:
        typer.echo(f"Error: {error}", err=True)
        raise typer.Exit(code=1) from error
    summary = asyncio.run(
        evaluate_batch(rows, output_dir, jobs=jobs, dry_run=dry_run, report=_report)
    )
    typer.echo(_summary_line(summary, dry_run))
    if summary.failed:
        raise typer.Exit(code=1)
