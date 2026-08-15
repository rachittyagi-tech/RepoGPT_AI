"""
app/api/v1/system.py

System-level endpoints: health check and version info.
These are intentionally free of business logic — Step 3+ will add
domain routers (auth, repositories, chat) alongside this one.
"""

from datetime import datetime, timezone

from fastapi import APIRouter
from pydantic import BaseModel

from app.core.settings import settings

router = APIRouter(tags=["System"])


class HealthResponse(BaseModel):
    status: str
    timestamp: datetime
    environment: str


class VersionResponse(BaseModel):
    app_name: str
    version: str
    api_prefix: str


@router.get("/health", response_model=HealthResponse, summary="Liveness/health probe")
async def health_check() -> HealthResponse:
    """
    Returns basic service health. Used by Docker/Kubernetes liveness
    and readiness probes, and load balancer health checks.

    NOTE: Step 2 does not yet check DB/Redis/ChromaDB connectivity —
    that will be added once those integrations exist (Step 3+), turning
    this into a full readiness probe (`/health/ready`).
    """
    return HealthResponse(
        status="healthy",
        timestamp=datetime.now(timezone.utc),
        environment=settings.APP_ENV,
    )


@router.get("/version", response_model=VersionResponse, summary="Application version info")
async def get_version() -> VersionResponse:
    """Returns application name, semantic version, and active API prefix."""
    return VersionResponse(
        app_name=settings.APP_NAME,
        version=settings.APP_VERSION,
        api_prefix=settings.API_V1_PREFIX,
    )
