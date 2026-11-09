"""Public Python package for Maturity meter.

The package exports the small public API that other Python code can import.
Implementation details live in named modules and subpackages such as
``services``.
"""

from importlib.metadata import PackageNotFoundError, version

from maturity_meter.services.processing import (
    ProcessingResult,
    process_text,
)

try:
    # Package metadata is the version source of truth after installation.
    __version__ = version("maturity-meter")
except PackageNotFoundError:
    # Source-tree imports can occur before the project is installed.
    __version__ = "0+unknown"

# Keep the public import surface explicit so downstream users can see which
# names are intended to be stable.
__all__ = [
    "ProcessingResult",
    "__version__",
    "process_text",
]
