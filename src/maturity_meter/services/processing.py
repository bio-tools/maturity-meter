"""Reusable processing service for Maturity meter.

Service modules contain project logic behind public entry points. Keep
framework-specific parsing, rendering, and transport details outside this layer.
"""

import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ProcessingResult:
    """Result returned by the processing service.

    Parameters
    ----------
    input_text : str
        Text received from a public entry point.
    output_text : str
        Processed text returned to the caller.
    """

    input_text: str
    output_text: str


def process_text(text: str) -> ProcessingResult:
    """Process text through the reusable service layer.

    Parameters
    ----------
    text : str
        Input text to process.

    Returns
    -------
    ProcessingResult
        Processed result.
    """
    # This starter transformation is intentionally simple. Replace the body of
    # this function with the real project logic while keeping the typed result.
    logger.debug("Processing text input")
    return ProcessingResult(input_text=text, output_text=text.upper())


def make_upper(text: str) -> str:
    """Convert input text to uppercase.

    Parameters
    ----------
    text : str
        Input text to convert.

    Returns
    -------
    str
        Uppercase text.

    Examples
    --------
    >>> make_upper("abc")
    'ABC'
    """
    # Keep this small helper as a thin wrapper so processing behavior has one
    # implementation.
    return process_text(text).output_text
