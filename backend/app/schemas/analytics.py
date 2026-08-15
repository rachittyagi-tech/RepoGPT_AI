"""
app/schemas/analytics.py

Pydantic v2 request/response DTOs for the Repository Analytics & AI
Insights Dashboard (Step 12). Every schema here is a read-only,
derived VIEW over data already produced by Steps 3-9 (GitHub, Scanner,
Chunking, Embeddings, Vector Store, RAG, Chat) — this module defines no
new source-of-truth data, only aggregations/shapes for presentation.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Shared enums
# ---------------------------------------------------------------------------
class PipelineStage(str, Enum):
    """Where a repository currently sits in the Clone -> Scan -> Chunk ->
    Embed -> Index pipeline. Drives `IndexStatusCard` / progress bars."""

    NOT_CLONED = "not_cloned"
    CLONED = "cloned"
    SCANNED = "scanned"
    CHUNKED = "chunked"
    EMBEDDED = "embedded"
    INDEXED = "indexed"


class HealthGrade(str, Enum):
    A = "A"
    B = "B"
    C = "C"
    D = "D"
    F = "F"


class ActivityEventType(str, Enum):
    CLONED = "cloned"
    UPDATED = "updated"
    SCANNED = "scanned"
    CHUNKED = "chunked"
    EMBEDDED = "embedded"
    INDEXED = "indexed"
    CHAT_MESSAGE = "chat_message"


# ---------------------------------------------------------------------------
# Repository Overview — GET /api/analytics/repository/{repository}
# ---------------------------------------------------------------------------
class RepositoryOverview(BaseModel):
    repository_name: str
    owner: str
    repo: str
    size_mb: Optional[float] = None
    age_days: Optional[int] = Field(default=None, description="Days since the repository was first cloned.")
    cloned_at: Optional[datetime] = None
    last_updated_at: Optional[datetime] = None
    last_indexed_at: Optional[datetime] = Field(
        default=None, description="Timestamp of the most recent successful vector-index run, if any."
    )
    files_indexed: int = 0
    chunks_created: int = 0
    embeddings_generated: int = 0
    vector_count: int = 0
    health_score: Optional[float] = Field(default=None, description="0-100 overall health score.")
    pipeline_stage: PipelineStage = PipelineStage.CLONED


# ---------------------------------------------------------------------------
# Language stats — GET /api/analytics/languages/{repository}
# ---------------------------------------------------------------------------
class LanguageStat(BaseModel):
    language: str
    file_count: int
    percentage: float = Field(..., description="Share of total files, 0-100.")
    lines_of_code: int


class FileSizeEntry(BaseModel):
    relative_path: str
    language: str
    size_bytes: int
    line_count: int


class LanguageStatsResponse(BaseModel):
    success: bool = True
    repository_name: str
    total_files: int
    total_lines_of_code: int
    languages: List[LanguageStat]
    most_active_languages: List[str] = Field(
        default_factory=list, description="Top 3 languages by file count, most active first."
    )
    largest_files: List[FileSizeEntry] = Field(default_factory=list)
    smallest_files: List[FileSizeEntry] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Health score — GET /api/analytics/health/{repository}
# ---------------------------------------------------------------------------
class HealthScoreBreakdown(BaseModel):
    documentation_score: float = Field(..., ge=0, le=100)
    structure_score: float = Field(..., ge=0, le=100)
    comments_score: float = Field(..., ge=0, le=100)
    complexity_score: float = Field(..., ge=0, le=100)
    test_coverage_score: float = Field(..., ge=0, le=100)


class HealthScoreResponse(BaseModel):
    success: bool = True
    repository_name: str
    overall_score: float = Field(..., ge=0, le=100)
    grade: HealthGrade
    breakdown: HealthScoreBreakdown
    recommendations: List[str] = Field(default_factory=list)
    calculated_at: datetime


# ---------------------------------------------------------------------------
# Index status — embedded in dashboard + repository views
# ---------------------------------------------------------------------------
class IndexStatus(BaseModel):
    repository_name: str
    stage: PipelineStage
    progress_percentage: float = Field(..., ge=0, le=100)
    files_indexed: int = 0
    chunks_created: int = 0
    embeddings_generated: int = 0
    vectors_indexed: int = 0
    last_indexed_at: Optional[datetime] = None


# ---------------------------------------------------------------------------
# Activity timeline — GET /api/analytics/activity
# ---------------------------------------------------------------------------
class ActivityEvent(BaseModel):
    repository_name: str
    event_type: ActivityEventType
    timestamp: datetime
    detail: str


class ActivityTimelineResponse(BaseModel):
    success: bool = True
    count: int
    events: List[ActivityEvent]


# ---------------------------------------------------------------------------
# AI usage insights — GET /api/analytics/usage
# ---------------------------------------------------------------------------
class QuestionFrequency(BaseModel):
    question: str
    count: int


class AIUsageInsights(BaseModel):
    total_chat_requests: int = 0
    total_conversations: int = 0
    average_response_time_seconds: float = 0.0
    average_retrieval_time_seconds: float = 0.0
    average_similarity_score: float = 0.0
    total_embeddings_generated: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    estimated_cost_usd: float = Field(
        default=0.0,
        description="Rough estimate only, based on a configurable $/1K-token rate — not a billing figure.",
    )
    most_asked_questions: List[QuestionFrequency] = Field(default_factory=list)


class UsageResponse(BaseModel):
    success: bool = True
    scope: str = Field(..., description="'all' or a specific repository_name.")
    usage: AIUsageInsights
    generated_at: datetime


# ---------------------------------------------------------------------------
# Dashboard — GET /api/analytics/dashboard
# ---------------------------------------------------------------------------
class DashboardTotals(BaseModel):
    total_repositories: int
    total_files_indexed: int
    total_chunks_created: int
    total_embeddings_generated: int
    total_vectors: int
    average_health_score: Optional[float] = None


class DashboardResponse(BaseModel):
    success: bool = True
    totals: DashboardTotals
    repositories: List[RepositoryOverview]
    language_distribution: Dict[str, int] = Field(
        default_factory=dict, description="File count per language, aggregated across ALL repositories."
    )
    ai_usage: AIUsageInsights
    recent_activity: List[ActivityEvent] = Field(default_factory=list)
    generated_at: datetime


class RepositoryAnalyticsResponse(BaseModel):
    success: bool = True
    overview: RepositoryOverview
    index_status: IndexStatus
    language_stats: LanguageStatsResponse
    health: HealthScoreResponse
    generated_at: datetime
