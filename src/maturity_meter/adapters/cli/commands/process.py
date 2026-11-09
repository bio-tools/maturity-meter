"""Text-processing command for the Typer CLI adapter.

The command layer owns command-line arguments, help text, and terminal output.
It delegates project logic to the service layer so command behavior is easy to
test.
"""

import typer

from maturity_meter.services.processing import evaluate_maturity


def run(text: str) -> str:
    """Run the command logic without printing to the terminal.

    Parameters
    ----------
    text : str
        Input text to process.

    Returns
    -------
    str
        Processed output text.
    """
    # Keeping command logic in a pure helper makes it straightforward to test
    # without capturing terminal output.
    return str(evaluate_maturity().maturity_placeholder)


def command(
    text: str = typer.Argument(
        "Maturity meter",
        help="Text to process.",
    ),
) -> None:
    """Process text from the command line and print the result.

    Parameters
    ----------
    text : str
        Input text to process.
    """
    # Typer handles parsing and validation; the command only prints the service
    # result in a human-friendly way.
    typer.echo(run(text))
