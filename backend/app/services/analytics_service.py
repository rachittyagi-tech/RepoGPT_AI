"""
app/services/analytics_service.py

Orchestrates the Repository Analytics & AI Insights Dashboard (Step 12).

Sequences 5 collaborators — `GitHubService` (repo metadata), `ScannerService`
(files/languages), `StatisticsService` (pipeline-stage aggregation +
AI usage), `RepositoryHealthService` (health score), `VectorStoreService`
(vector counts) — the same orchestration-only pattern already used by
`RAGService` (Step 8) and `ChatService` (Step 9): this class owns *order*,
never duplicates any collaborator's own logic.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Dict, List, Optional

from fastapi import Depends

from app.core.exceptions import ScanNotPerformedError
from app.core.logging import get_logger
from app.schemas.analytics import (
    ActivityEvent,
    ActivityEventType,
    ActivityTimelineResponse,
    DashboardResponse,
    DashboardTotals,
    FileSizeEntry,
    LanguageStat,
    LanguageStatsResponse,
    RepositoryAnalyticsResponse,
    RepositoryOverview,
    UsageResponse,
)
from app.schemas.github import RepositoryInfo
from app.services.conversation_service import ConversationService, get_conversation_service
from app.services.github_service import GitHubService, get_github_service
from app.services.repository_health_service import RepositoryHealthService, get_repository_health_service
from app.services.scanner_service import ScannerService, get_scanner_service
from app.services.statistics_service import StatisticsService, UsageMetricsRecorder, get_statistics_service

logger = get_logger("services.analytics")

_MAX_TOP_FILES = 5
_MAX_ACTIVITY_EVENTS = 50


class AnalyticsService:
    """Builds every Repository Analytics & AI Insights Dashboard response."""

    def __init__(
        self,
        github_service: GitHubService,
        scanner_service: ScannerService,
        statistics_service: StatisticsService,
        health_service: RepositoryHealthService,
        conversation_service: ConversationService,
    ) -> None:
        self.github_service = github_service
        self.scanner_service = scanner_service
        self.statistics_service = statistics_service
        self.health_service = health_service
        self.conversation_service = conversation_service

    # ------------------------------------------------------------------
    # GET /api/analytics/dashboard
    # ------------------------------------------------------------------
    async def get_dashboard(self) -> DashboardResponse:
        repo_infos = await self.github_service.list_repositories()

        overviews: List[RepositoryOverview] = []
        language_totals: Dict[str, int] = {}
        events: List[ActivityEvent] = []

        for info in repo_infos:
            overview = await self._build_overview(info)
            overviews.append(overview)

            try:
                stats = self.scanner_service.get_cached_statistics(info.repository_name)
                for lang, count in stats.language_counts.items():
                    language_totals[lang] = language_totals.get(lang, 0) + count
            except ScanNotPerformedError:
                pass

            events.extend(self._repository_events(info))

        events.sort(key=lambda e: e.timestamp, reverse=True)

        health_scores = [o.health_score for o in overviews if o.health_score is not None]
        avg_health = round(sum(health_scores) / len(health_scores), 1) if health_scores else None

        totals = DashboardTotals(
            total_repositories=len(overviews),
            total_files_indexed=sum(o.files_indexed for o in overviews),
            total_chunks_created=sum(o.chunks_created for o in overviews),
            total_embeddings_generated=sum(o.embeddings_generated for o in overviews),
            total_vectors=sum(o.vector_count for o in overviews),
            average_health_score=avg_health,
        )

        ai_usage = UsageMetricsRecorder.get_insights(
            repository_name=None, total_conversations=self._total_conversation_count()
        )
        ai_usage.total_embeddings_generated = totals.total_embeddings_generated

        return DashboardResponse(
            totals=totals,
            repositories=overviews,
            language_distribution=language_totals,
            ai_usage=ai_usage,
            recent_activity=events[:_MAX_ACTIVITY_EVENTS],
            generated_at=datetime.now(timezone.utc),
        )

    # ------------------------------------------------------------------
    # GET /api/analytics/repository/{repository}
    # ------------------------------------------------------------------
    async def get_repository_analytics(self, repository_name: str) -> RepositoryAnalyticsResponse:
        info = await self.github_service.get_repository_status(repository_name)
        overview = await self._build_overview(info)
        index_status = await self.statistics_service.get_index_status(repository_name)
        language_stats = await self.get_language_stats(repository_name)
        health = await self.health_service.calculate_health_score(repository_name)

        return RepositoryAnalyticsResponse(
            overview=overview,
            index_status=index_status,
            language_stats=language_stats,
            health=health,
            generated_at=datetime.now(timezone.utc),
        )

    # ------------------------------------------------------------------
    # GET /api/analytics/languages/{repository}
    # ------------------------------------------------------------------
    async def get_language_stats(self, repository_name: str) -> LanguageStatsResponse:
        try:
            stats = self.scanner_service.get_cached_statistics(repository_name)
            files = self.scanner_service.get_cached_files(repository_name)
        except ScanNotPerformedError:
            return LanguageStatsResponse(
                repository_name=repository_name,
                total_files=0,
                total_lines_of_code=0,
                languages=[],
            )

        lines_by_language: Dict[str, int] = {}
        for f in files:
            lines_by_language[f.language] = lines_by_language.get(f.language, 0) + f.line_count

        total_files = stats.supported_files or 1  # guard against div-by-zero below
        languages = [
            LanguageStat(
                language=lang,
                file_count=count,
                percentage=round((count / total_files) * 100, 1),
                lines_of_code=lines_by_language.get(lang, 0),
            )
            for lang, count in sorted(stats.language_counts.items(), key=lambda kv: kv[1], reverse=True)
        ]

        most_active = [lang.language for lang in languages[:3]]

        sorted_by_size = sorted(files, key=lambda f: f.size_bytes, reverse=True)
        largest = [self._to_file_entry(f) for f in sorted_by_size[:_MAX_TOP_FILES]]
        smallest = (
            [self._to_file_entry(f) for f in sorted_by_size[-_MAX_TOP_FILES:][::-1]] if sorted_by_size else []
        )

        return LanguageStatsResponse(
            repository_name=repository_name,
            total_files=stats.supported_files,
            total_lines_of_code=stats.total_lines_of_code,
            languages=languages,
            most_active_languages=most_active,
            largest_files=largest,
            smallest_files=smallest,
        )

    # ------------------------------------------------------------------
    # GET /api/analytics/activity
    # ------------------------------------------------------------------
    async def get_activity_timeline(self, limit: int = _MAX_ACTIVITY_EVENTS) -> ActivityTimelineResponse:
        repo_infos = await self.github_service.list_repositories()
        events: List[ActivityEvent] = []
        for info in repo_infos:
            events.extend(self._repository_events(info))
        events.sort(key=lambda e: e.timestamp, reverse=True)
        limited = events[:limit]
        return ActivityTimelineResponse(count=len(limited), events=limited)

    # ------------------------------------------------------------------
    # GET /api/analytics/usage
    # ------------------------------------------------------------------
    async def get_usage_insights(self, repository_name: Optional[str] = None) -> UsageResponse:
        conversation_count = self._total_conversation_count(repository_name)
        usage = UsageMetricsRecorder.get_insights(
            repository_name=repository_name, total_conversations=conversation_count
        )
        return UsageResponse(
            scope=repository_name or "all",
            usage=usage,
            generated_at=datetime.now(timezone.utc),
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    async def _build_overview(self, info: RepositoryInfo) -> RepositoryOverview:
        index_status = await self.statistics_service.get_index_status(info.repository_name)

        health_score: Optional[float] = None
        try:
            health = await self.health_service.calculate_health_score(info.repository_name)
            health_score = health.overall_score
        except Exception:  # noqa: BLE001 — health is best-effort for the overview card
            logger.debug("Health score unavailable for %s", info.repository_name)

        age_days: Optional[int] = None
        if info.cloned_at is not None:
            age_days = (datetime.now(timezone.utc) - info.cloned_at).days

        return RepositoryOverview(
            repository_name=info.repository_name,
            owner=info.owner,
            repo=info.repo,
            size_mb=info.size_mb,
            age_days=age_days,
            cloned_at=info.cloned_at,
            last_updated_at=info.last_updated_at,
            last_indexed_at=index_status.last_indexed_at,
            files_indexed=index_status.files_indexed,
            chunks_created=index_status.chunks_created,
            embeddings_generated=index_status.embeddings_generated,
            vector_count=index_status.vectors_indexed,
            health_score=health_score,
            pipeline_stage=index_status.stage,
        )

    def _repository_events(self, info: RepositoryInfo) -> List[ActivityEvent]:
        events: List[ActivityEvent] = []
        if info.cloned_at:
            events.append(
                ActivityEvent(
                    repository_name=info.repository_name,
                    event_type=ActivityEventType.CLONED,
                    timestamp=info.cloned_at,
                    detail=f"Repository '{info.repository_name}' was cloned.",
                )
            )
        if info.last_updated_at and info.last_updated_at != info.cloned_at:
            events.append(
                ActivityEvent(
                    repository_name=info.repository_name,
                    event_type=ActivityEventType.UPDATED,
                    timestamp=info.last_updated_at,
                    detail=f"Repository '{info.repository_name}' was updated (latest commit pulled).",
                )
            )

        last_run = self.statistics_service.vector_store_service.get_last_index_run(info.repository_name)
        if last_run is not None:
            events.append(
                ActivityEvent(
                    repository_name=info.repository_name,
                    event_type=ActivityEventType.INDEXED,
                    timestamp=last_run.indexed_at,
                    detail=f"Indexed {last_run.vectors_indexed} vectors into ChromaDB.",
                )
            )
        return events

    def _total_conversation_count(self, repository_name: Optional[str] = None) -> int:
        return self.conversation_service.count_conversations(repository_name)

    @staticmethod
    def _to_file_entry(f) -> FileSizeEntry:
        return FileSizeEntry(
            relative_path=f.relative_path,
            language=f.language,
            size_bytes=f.size_bytes,
            line_count=f.line_count,
        )


def get_analytics_service(
    github_service: GitHubService = Depends(get_github_service),
    scanner_service: ScannerService = Depends(get_scanner_service),
    statistics_service: StatisticsService = Depends(get_statistics_service),
    health_service: RepositoryHealthService = Depends(get_repository_health_service),
    conversation_service: ConversationService = Depends(get_conversation_service),
) -> AnalyticsService:
    """FastAPI dependency provider — see app/api/analytics.py."""
    return AnalyticsService(
        github_service=github_service,
        scanner_service=scanner_service,
        statistics_service=statistics_service,
        health_service=health_service,
        conversation_service=conversation_service,
    )
