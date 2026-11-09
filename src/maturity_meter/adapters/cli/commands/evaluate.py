"""Maturity evaluation command for the Typer CLI adapter.

The command layer owns command-line arguments, help text, and terminal output.
It delegates project logic to the service layer so command behavior is easy to
test.
"""

import typer

from maturity_meter.services.processing import evaluate_maturity


def run() -> str:
    """Run the command logic without printing to the terminal.

    Returns
    -------
    str
        Evaluated maturity as text.
    """
    # Keeping command logic in a pure helper makes it straightforward to test
    # without capturing terminal output.
    return str(evaluate_maturity().maturity_placeholder)


def command() -> None:
    """Evaluate maturity and print the result."""
    typer.echo(run())
