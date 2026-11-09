"""Evaluation routes for the web API adapter.

Routes translate HTTP requests into service calls. They should validate and
shape API payloads without duplicating domain logic.
"""

from fastapi import APIRouter

from maturity_meter.services.processing import MaturityResult, evaluate_maturity

router = APIRouter(tags=["evaluation"])


@router.get("/evaluate", response_model=MaturityResult)
def evaluate() -> MaturityResult:
    """Evaluate maturity through the service layer.

    Returns
    -------
    MaturityResult
        Evaluation result from the service.
    """
    # The service result is already the public response shape, so return it
    # directly instead of duplicating it in a separate schema.
    return evaluate_maturity()
