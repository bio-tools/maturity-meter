"""Runtime entry point for ``python -m maturity_meter``.

This module provides a tiny package-level command for quick smoke tests. Keep
larger runtime interfaces in dedicated modules.
"""

from maturity_meter.logging_config import configure_logging
from maturity_meter.services.processing import evaluate_maturity


def main() -> None:
    """Run the package entry point."""
    configure_logging()
    # Delegate to the service layer so the entry point stays small and
    # testable.
    result = evaluate_maturity()
    print(result.maturity_placeholder)


if __name__ == "__main__":
    main()
