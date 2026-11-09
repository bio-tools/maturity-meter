"""Health-check routes for the web API adapter.

Health routes give deployment platforms and monitoring tools a lightweight way
to check whether the application process is responding.
"""

from fastapi import APIRouter

router = APIRouter(tags=["health"])


@router.get("/health")
def health() -> dict[str, str]:
    """Return service health status.

    Returns
    -------
    dict[str, str]
        Health status payload.
    """
    # Keep this endpoint cheap: it should not run expensive project logic.
    return {"status": "ok"}
