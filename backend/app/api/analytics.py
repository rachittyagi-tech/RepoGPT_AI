"""
app/api/analytics.py

HTTP layer for the Repository Analytics & AI Insights Dashboard (Step 12).

Thin router only — every endpoint delegates entirely to `AnalyticsService`.
All 6 routes are read-only (GET) views over data already produced by
Steps 3-9; none of them trigger a scan/chunk/embed/index run themselves.
"""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Query, status

from app.core.logging import get_logger
from app.schemas.analytics import (
    ActivityTimelineResponse,
    DashboardResponse,
    HealthScoreResponse,
    LanguageStatsResponse,
    RepositoryAnalyticsResponse,
    UsageResponse,
)
from app.services.analytics_service import AnalyticsService, get_analytics_service
from app.services.repository_health_service import RepositoryHealthService, get_repository_health_service

logger = get_logger("api.analytics")

router = APIRouter(tags=["Analytics"])


@router.get(
    "/dashboard",
    response_model=DashboardResponse,
    status_code=status.HTTP_200_OK,
    summary="Overview dashboard across every locally-stored repository",
)
async def get_dashboard(
    service: AnalyticsService = Depends(get_analytics_service),
) -> DashboardResponse:
    """Aggregate totals, per-repository overviews, language distribution, AI usage,
    and recent activity — everything `Analytics.tsx`'s top-level view needs in one call."""
    return await service.get_dashboard()


@router.get(
    "/repository/{repository}",
    response_model=RepositoryAnalyticsResponse,
    status_code=status.HTTP_200_OK,
    summary="Full analytics for a single repository",
)
async def get_repository_analytics(
    repository: str,
    service: AnalyticsService = Depends(get_analytics_service),
) -> RepositoryAnalyticsResponse:
    """Combines overview, pipeline index status, language stats, and health score
    for one repository. Returns 404 if the repository isn't cloned locally."""
    return await service.get_repository_analytics(repository)


@router.get(
    "/languages/{repository}",
    response_model=LanguageStatsResponse,
    status_code=status.HTTP_200_OK,
    summary="Language distribution and file-size extremes for a repository",
)
async def get_language_stats(
    repository: str,
    service: AnalyticsService = Depends(get_analytics_service),
) -> LanguageStatsResponse:
    """Powers `LanguageChart.tsx`. Returns an all-zero response (not a 404) if the
    repository hasn't been scanned yet — scan it via /api/scanner/scan first."""
    return await service.get_language_stats(repository)


@router.get(
    "/health/{repository}",
    response_model=HealthScoreResponse,
    status_code=status.HTTP_200_OK,
    summary="Heuristic repository health score (0-100) with a category breakdown",
)
async def get_repository_health(
    repository: str,
    health_service: RepositoryHealthService = Depends(get_repository_health_service),
) -> HealthScoreResponse:
    """See `RepositoryHealthService` module docstring — this is a heuristic
    estimate (documentation/structure/comments/complexity/test-coverage
    signals), not output from a real static-analysis tool."""
    return await health_service.calculate_health_score(repository)


@router.get(
    "/activity",
    response_model=ActivityTimelineResponse,
    status_code=status.HTTP_200_OK,
    summary="Recent activity across all repositories (clone/update/index events)",
)
async def get_activity_timeline(
    limit: int = Query(default=50, ge=1, le=200, description="Max events to return, most recent first."),
    service: AnalyticsService = Depends(get_analytics_service),
) -> ActivityTimelineResponse:
    """Powers `ActivityTimeline.tsx`."""
    return await service.get_activity_timeline(limit=limit)


@router.get(
    "/usage",
    response_model=UsageResponse,
    status_code=status.HTTP_200_OK,
    summary="AI chat usage insights (response times, tokens, most-asked questions)",
)
async def get_usage_insights(
    repository: Optional[str] = Query(
        default=None, description="Scope to one repository's chat usage; omit for usage across all repos."
    ),
    service: AnalyticsService = Depends(get_analytics_service),
) -> UsageResponse:
    """Powers `AIUsageCard.tsx`. Token/cost/response-time figures only reflect chat
    activity that happened during this backend process's current lifetime
    (in-memory counters, same as the rest of the pipeline's statistics)."""
    return await service.get_usage_insights(repository_name=repository)
