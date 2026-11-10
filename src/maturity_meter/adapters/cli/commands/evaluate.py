"""Maturity evaluation command for the Typer CLI adapter.

The command layer owns command-line arguments, help text, and terminal output.
It delegates project logic to the service layer so command behavior is easy to
test.
"""

import asyncio
import json
from pathlib import Path
from typing import Annotated

import typer
from pydantic import ValidationError

from maturity_meter.models import EvaluationRequest
from maturity_meter.services.ingestion import RepositoryFetchError, ingest
from maturity_meter.services.processing import score


def run(
    request: EvaluationRequest,
    output: Path | None = None,
    save_data: Path | None = None,
) -> str:
    """Run the command logic without printing to the terminal.

    Parameters
    ----------
    request : EvaluationRequest
        Repository and optional publication/bio.tools identifiers.
    output : pathlib.Path, optional
        File to also save the result to, as JSON.
    save_data : pathlib.Path, optional
        File to save the ingested data to, as JSON (reusable with ``--data``).

    Returns
    -------
    str
        The result as JSON.
    """
    # Keeping command logic in a pure helper makes it straightforward to test
    # without capturing terminal output.
    data = asyncio.run(ingest(request))
    if save_data is not None:
        data.save(save_data)
    result = score(data)
    if output is not None:
        result.save(output)
    return result.to_json()


def command(
    repository: Annotated[
        str, typer.Argument(help="URL of a GitHub or GitLab (any instance) repository.")
    ],
    doi: Annotated[
        list[str] | None,
        typer.Option("--doi", help="DOI of a related publication (repeatable)."),
    ] = None,
    biotools_id: Annotated[
        str | None,
        typer.Option("--biotools-id", help="bio.tools identifier of the software."),
    ] = None,
    data: Annotated[
        Path | None,
        typer.Option(
            "--data",
            exists=True,
            dir_okay=False,
            help=(
                "JSON file with already-fetched data, e.g. one written by "
                "--save-data. Sources present in it are not fetched."
            ),
        ),
    ] = None,
    output: Annotated[
        Path | None,
        typer.Option(
            "--output",
            "-o",
            dir_okay=False,
            help="Also save the result to this file as JSON.",
        ),
    ] = None,
    save_data: Annotated[
        Path | None,
        typer.Option(
            "--save-data",
            dir_okay=False,
            help="Save the ingested data to this file as JSON (reusable with --data).",
        ),
    ] = None,
) -> None:
    """Evaluate maturity of a repository and print the result as JSON."""
    try:
        request = EvaluationRequest(
            repository=repository,
            dois=doi or [],
            biotools_id=biotools_id,
            data=json.loads(data.read_text()) if data else {},
        )
    except (ValidationError, json.JSONDecodeError) as error:
        raise typer.BadParameter(str(error)) from error
    try:
        typer.echo(run(request, output, save_data))
    except RepositoryFetchError as error:
        typer.echo(f"Error: {error}", err=True)
        raise typer.Exit(code=1) from error
