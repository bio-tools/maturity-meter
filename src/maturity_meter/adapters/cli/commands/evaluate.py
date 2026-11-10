"""Maturity evaluation command for the Typer CLI adapter.

The command layer owns command-line arguments, help text, and terminal output.
It delegates project logic to the service layer so command behavior is easy to
test.
"""

import asyncio
from typing import Annotated

import typer
from pydantic import ValidationError

from maturity_meter.models import EvaluationRequest
from maturity_meter.services.processing import evaluate_maturity


def run(request: EvaluationRequest) -> str:
    """Run the command logic without printing to the terminal.

    Parameters
    ----------
    request : EvaluationRequest
        Repository and optional publication/bio.tools identifiers.

    Returns
    -------
    str
        Evaluated maturity as text.
    """
    # Keeping command logic in a pure helper makes it straightforward to test
    # without capturing terminal output.
    return str(asyncio.run(evaluate_maturity(request)).maturity_placeholder)


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
) -> None:
    """Evaluate maturity of a repository and print the result."""
    try:
        request = EvaluationRequest(
            repository=repository, dois=doi or [], biotools_id=biotools_id
        )
    except ValidationError as error:
        raise typer.BadParameter(str(error)) from error
    typer.echo(run(request))
