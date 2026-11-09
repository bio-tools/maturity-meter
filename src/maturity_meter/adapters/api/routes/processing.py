"""Processing routes for the web API adapter.

Routes translate HTTP requests into service calls. They should validate and
shape API payloads without duplicating domain logic.
"""

from fastapi import APIRouter

from maturity_meter.adapters.api.schemas import (
    ProcessRequest,
    ProcessResponse,
)
from maturity_meter.services.processing import evaluate_maturity

router = APIRouter(tags=["processing"])


@router.post("/process", response_model=ProcessResponse)
def process(request: ProcessRequest) -> ProcessResponse:
    """Process text through the service layer.

    Parameters
    ----------
    request : ProcessRequest
        Request payload.

    Returns
    -------
    ProcessResponse
        Processed response payload.
    """
    # Route handlers call services and then map service results back into API
    # response schemas.
    result = evaluate_maturity()
    return ProcessResponse(
        input_text=request.text,
        output_text=str(result.maturity_placeholder),
    )
