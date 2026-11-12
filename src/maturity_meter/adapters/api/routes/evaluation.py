"""Evaluation routes for the web API adapter.

Routes translate HTTP requests into service calls. They should validate and
shape API payloads without duplicating domain logic.
"""

import asyncio
from typing import Literal

from fastapi import APIRouter, HTTPException, Response

from maturity_meter.models import EvaluationRequest
from maturity_meter.services.ingestion import RepositoryFetchError
from maturity_meter.services.processing import MaturityResult, evaluate_maturity
from maturity_meter.services.radial_mosaic import render_svg

router = APIRouter(tags=["evaluation"])

# HTTP status for each way fetching the repository can fail.
_STATUS_BY_REASON = {
    "not_found": 404,
    "forbidden": 403,
    "rate_limited": 429,
    "unsupported": 422,
    "unreachable": 502,
}
_FETCH_ERRORS = {
    status: {"description": "Repository could not be fetched"}
    for status in (403, 404, 422, 429, 502)
}


async def _evaluate(request: EvaluationRequest) -> MaturityResult:
    """Evaluate, turning repository fetch failures into HTTP errors."""
    try:
        return await evaluate_maturity(request)
    except RepositoryFetchError as error:
        raise HTTPException(
            status_code=_STATUS_BY_REASON[error.reason], detail=str(error)
        ) from error


@router.post("/evaluate", response_model=MaturityResult, responses=_FETCH_ERRORS)
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
    return await _evaluate(request)


@router.post(
    "/evaluate/mosaic",
    response_class=Response,
    responses={
        200: {"content": {"image/svg+xml": {}}, "description": "Radial mosaic"},
        503: {"description": "The mosaic renderer is not available"},
        **_FETCH_ERRORS,
    },
)
async def evaluate_mosaic(
    request: EvaluationRequest, per: Literal["dimension", "metric"] = "dimension"
) -> Response:
    """Evaluate maturity and return it as a radial mosaic SVG.

    Parameters
    ----------
    request : EvaluationRequest
        Repository and optional publication/bio.tools identifiers.
    per : {"dimension", "metric"}, default="dimension"
        One ray per dimension or per metric.

    Returns
    -------
    fastapi.Response
        The SVG: ray length is the score, opacity the coverage.
    """
    result = await _evaluate(request)
    try:
        # Rendering runs a Node process; keep it off the event loop.
        svg = await asyncio.to_thread(render_svg, result.maturity, per)
    except RuntimeError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error
    return Response(content=svg, media_type="image/svg+xml")
