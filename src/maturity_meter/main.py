"""Runtime entry point for ``python -m maturity_meter``.

This module provides a tiny package-level command for quick smoke tests. Keep
larger runtime interfaces in dedicated modules.
"""

import asyncio
import sys

from pydantic import ValidationError

from maturity_meter.logging_config import configure_logging
from maturity_meter.models import EvaluationRequest
from maturity_meter.services.ingestion import RepositoryFetchError
from maturity_meter.services.processing import evaluate_maturity


def main() -> None:
    """Run the package entry point.

    Evaluates the repository URL given as the first command-line argument. Use
    the ``maturity-meter`` command for DOIs and bio.tools IDs.
    """
    if len(sys.argv) != 2:
        sys.exit("usage: python -m maturity_meter <repository-url>")
    configure_logging()
    # Delegate to the service layer so the entry point stays small and
    # testable.
    try:
        request = EvaluationRequest(repository=sys.argv[1])
    except ValidationError as error:
        reason = error.errors()[0]["msg"]
        sys.exit(f"Error: invalid repository URL {sys.argv[1]!r}: {reason}")
    try:
        result = asyncio.run(evaluate_maturity(request))
    except RepositoryFetchError as error:
        sys.exit(f"Error: {error}")
    print(result.to_json())


if __name__ == "__main__":
    main()
