"""Typer command-line application for Maturity meter.

The CLI adapter translates command-line input into calls to reusable project
services. Command modules stay small so they are easy to test separately from
terminal formatting.
"""

import typer

from maturity_meter.adapters.cli.commands import batch, evaluate, lineage, overview
from maturity_meter.logging_config import configure_logging

# The Typer app is the command registry. Add new commands by importing their
# modules and registering them below.
app = typer.Typer(help="Automated maturity model for research software tools")


@app.callback()
def root() -> None:
    """Run the application's subcommands."""


app.command(name="evaluate")(evaluate.command)
app.command(name="batch")(batch.command)
app.command(name="lineage")(lineage.command)
app.command(name="overview")(overview.command)


def main() -> None:
    """Run the command-line application."""
    configure_logging()
    app()
