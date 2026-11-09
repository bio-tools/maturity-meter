"""FastAPI application adapter for Maturity meter.

This module assembles API routes into a FastAPI application. Route modules
handle HTTP-specific concerns, while shared processing logic stays in the
service layer.
"""

from fastapi import FastAPI

from maturity_meter.adapters.api.routes import (
    health,
    processing,
)
from maturity_meter.config import Settings, get_settings


def create_app(settings: Settings | None = None) -> FastAPI:
    """Create and configure the web API application.

    Parameters
    ----------
    settings : Settings | None, optional
        Runtime settings. Cached environment settings are used when omitted.

    Returns
    -------
    fastapi.FastAPI
        Configured API application.
    """
    resolved_settings = settings or get_settings()

    # Application metadata is pulled from the generated project metadata so the
    # OpenAPI schema starts with useful names, versions, and descriptions.
    api = FastAPI(
        title="Maturity meter",
        version="0.1.0",
        description="Automated maturity model for research software tools",
        servers=(
            [{"url": str(resolved_settings.public_base_url).rstrip("/")}]
            if resolved_settings.public_base_url
            else None
        ),
    )
    api.state.settings = resolved_settings

    # Register small route modules here. Keeping registration explicit makes it
    # easy to see which API surfaces are included for this generated project.
    api.include_router(health.router)
    api.include_router(processing.router)

    return api


# Uvicorn and other ASGI servers discover this module-level application object.
app = create_app()
