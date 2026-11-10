"""Reusable processing service for Maturity meter.

Service modules contain project logic behind public entry points. Keep
framework-specific parsing, rendering, and transport details outside this layer.
"""

import logging
from dataclasses import dataclass
from typing import Any

from maturity_meter.components import combine
from maturity_meter.models import EvaluationRequest
from maturity_meter.services.ingestion import ingest

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class MaturityResult:
    """Result returned by the evaluation service."""

    maturity_placeholder: Any


async def evaluate_maturity(request: EvaluationRequest) -> MaturityResult:
    """Evaluate the maturity of the software described by ``request``.

    Parameters
    ----------
    request : EvaluationRequest
        Repository and optional publication/bio.tools identifiers.

    Returns
    -------
    MaturityResult
        Evaluated maturity.
    """
    logger.debug("Evaluating maturity of %s", request.repository)
    data = await ingest(request)
    return MaturityResult(maturity_placeholder=combine(data))
