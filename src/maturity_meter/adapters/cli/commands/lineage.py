"""Lineage command for the Typer CLI adapter.

Shows which ingested data and helper functions each metric uses, traced by
running the metrics on data saved with ``evaluate --save-data``.
"""

from pathlib import Path
from typing import Annotated

import typer
from pydantic import ValidationError

from maturity_meter.models import IngestedData
from maturity_meter.services.lineage import trace_lineage
from maturity_meter.services.lineage_figure import save_figure


def command(
    data: Annotated[
        list[Path],
        typer.Argument(
            exists=True,
            dir_okay=False,
            help=(
                "Data file(s) written by `evaluate --save-data`. Several files "
                "(e.g. from different tools) are merged for fuller coverage."
            ),
        ),
    ],
    output: Annotated[
        Path | None,
        typer.Option(
            "--output",
            "-o",
            dir_okay=False,
            help="Also save the lineage to this file as JSON.",
        ),
    ] = None,
    figure: Annotated[
        Path | None,
        typer.Option(
            "--figure",
            dir_okay=False,
            help=(
                "Save a flow figure (sources -> fields -> metrics -> dimensions): "
                "an HTML page for .html, Mermaid text otherwise (e.g. .mmd)."
            ),
        ),
    ] = None,
) -> None:
    """Trace which data and functions each metric uses; print it as JSON."""
    try:
        datasets = [IngestedData.load(path) for path in data]
    except ValidationError as error:
        raise typer.BadParameter(str(error)) from error
    lineage = trace_lineage(datasets)
    if output is not None:
        lineage.save(output)
    if figure is not None:
        save_figure(lineage, figure)
    typer.echo(lineage.to_json())
