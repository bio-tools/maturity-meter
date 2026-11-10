"""Runtime entry point for ``python -m maturity_meter``.

This module provides a tiny package-level command for quick smoke tests. Keep
larger runtime interfaces in dedicated modules.
"""

import asyncio
import sys

from maturity_meter.logging_config import configure_logging
from maturity_meter.models import EvaluationRequest
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
    request = EvaluationRequest(repository=sys.argv[1])
    result = asyncio.run(evaluate_maturity(request))
    print(result.maturity_placeholder)


if __name__ == "__main__":
    main()
