"""Overview command for the Typer CLI adapter.

Writes tables of every dimension, metric, source, weight and function, traced
by running the metrics on data saved with ``evaluate --save-data``.
"""

from pathlib import Path
from typing import Annotated

import typer
from pydantic import ValidationError

from maturity_meter.models import IngestedData
from maturity_meter.services.lineage import trace_lineage
from maturity_meter.services.overview import overview_markdown


def command(
    data: Annotated[
        list[Path],
        typer.Argument(
            exists=True,
            dir_okay=False,
            help=(
                "Data file(s) written by `evaluate --save-data`, e.g. the lineage "
                "probes in tests/fixtures/lineage, which exercise every metric."
            ),
        ),
    ],
    output: Annotated[
        Path | None,
        typer.Option(
            "--output",
            "-o",
            dir_okay=False,
            help="Save the overview to this Markdown file instead of printing it.",
        ),
    ] = None,
    ref: Annotated[
        str,
        typer.Option(
            "--ref",
            help="Commit, tag or branch the source code links point to.",
        ),
    ] = "main",
    repository: Annotated[
        str | None,
        typer.Option(
            "--repository",
            help="Source code URL for the links (default: the project's).",
        ),
    ] = None,
) -> None:
    """Write tables of all dimensions, metrics, sources, weights and functions."""
    try:
        datasets = [IngestedData.load(path) for path in data]
    except ValidationError as error:
        raise typer.BadParameter(str(error)) from error
    page = overview_markdown(trace_lineage(datasets), repository=repository, ref=ref)
    if output is None:
        typer.echo(page)
    else:
        output.write_text(page + "\n")
