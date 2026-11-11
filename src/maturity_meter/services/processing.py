"""Reusable processing service for Maturity meter.

Service modules contain project logic behind public entry points. Keep
framework-specific parsing, rendering, and transport details outside this layer.
"""

import logging
from pathlib import Path

from pydantic import BaseModel

from maturity_meter.components import combine
from maturity_meter.models import Evaluation, EvaluationRequest, IngestedData
from maturity_meter.services.ingestion import ingest

logger = logging.getLogger(__name__)


class MaturityResult(BaseModel):
    """Result returned by the evaluation service.

    Attributes
    ----------
    maturity : Evaluation
        Scores and metric results per dimension.
    """

    maturity: Evaluation

    def to_json(self) -> str:
        """Serialize the result as indented JSON.

        Returns
        -------
        str
            The result as JSON.
        """
        return self.model_dump_json(indent=2)

    def save(self, path: Path) -> None:
        """Write the result to ``path`` as indented JSON.

        Parameters
        ----------
        path : pathlib.Path
            File to write; it is overwritten if it exists.
        """
        path.write_text(self.to_json() + "\n")


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
    return score(await ingest(request))


def score(data: IngestedData) -> MaturityResult:
    """Score already-ingested data, without fetching anything.

    Parameters
    ----------
    data : IngestedData
        Data collected by :func:`~maturity_meter.services.ingestion.ingest`.

    Returns
    -------
    MaturityResult
        Evaluated maturity.
    """
    return MaturityResult(maturity=combine(data))
