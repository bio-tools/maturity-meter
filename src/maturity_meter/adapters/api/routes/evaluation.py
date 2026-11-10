"""Evaluation routes for the web API adapter.

Routes translate HTTP requests into service calls. They should validate and
shape API payloads without duplicating domain logic.
"""

from fastapi import APIRouter, HTTPException

from maturity_meter.models import EvaluationRequest
from maturity_meter.services.ingestion import RepositoryFetchError
from maturity_meter.services.processing import MaturityResult, evaluate_maturity

router = APIRouter(tags=["evaluation"])

# HTTP status for each way fetching the repository can fail.
_STATUS_BY_REASON = {
    "not_found": 404,
    "forbidden": 403,
    "rate_limited": 429,
    "unsupported": 422,
    "unreachable": 502,
}


@router.post(
    "/evaluate",
    response_model=MaturityResult,
    responses={
        status: {"description": "Repository could not be fetched"}
        for status in (403, 404, 422, 429, 502)
    },
)
async def evaluate(request: EvaluationRequest) -> MaturityResult:
    """Evaluate maturity through the service layer.

    Parameters
    ----------
    request : EvaluationRequest
        Repository and optional publication/bio.tools identifiers.

    Returns
    -------
    MaturityResult
        Evaluation result from the service.
    """
    # The service result is already the public response shape, so return it
    # directly instead of duplicating it in a separate schema.
    try:
        return await evaluate_maturity(request)
    except RepositoryFetchError as error:
        raise HTTPException(
            status_code=_STATUS_BY_REASON[error.reason], detail=str(error)
        ) from error
