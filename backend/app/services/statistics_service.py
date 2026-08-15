"""
app/services/statistics_service.py

Two responsibilities, kept in one module because they share the same
"in-memory, process-wide, read-mostly aggregation" shape (Step 12):

    1. `StatisticsService` — pulls each pipeline stage's already-cached
       statistics (Scanner/Chunking/Embedding/VectorStore, Step 4-7) for
       one repository into a single `IndexStatus` view, without
       re-running any of those stages.

    2. `UsageMetricsRecorder` — a lightweight, class-level counter that
       `ChatService` (Step 9) reports into after every chat interaction.
       This is the ONLY piece of Step 12 that writes to shared state
       (everything else here is read-only aggregation); it exists because
       "AI Usage Insights" (response time, token usage, most-asked
       questions) isn't derivable from data any earlier step persists.

Design notes (Clean Architecture / SOLID):
    - Never talks to FastAPI/HTTP. Raises nothing — pipeline stages that
      haven't run yet simply contribute zeros, so analytics degrades
      gracefully instead of erroring (a repo that's only been cloned still
      has a valid, if mostly-empty, analytics view).
    - Depends on the OTHER services' public cache-reader methods only
      (`get_cached_statistics`, `get_last_index_run`, etc.) — never reaches
      into their private `_CACHE` dicts directly (Dependency Inversion).
"""

from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
from typing import ClassVar, Dict, List, Optional

from fastapi import Depends

from app.core.exceptions import (
    ChunkingNotPerformedError,
    CollectionNotFoundError,
    EmbeddingsNotGeneratedError,
    ScanNotPerformedError,
)
from app.core.logging import get_logger
from app.schemas.analytics import AIUsageInsights, IndexStatus, PipelineStage, QuestionFrequency
from app.schemas.chat import TokenUsage
from app.services.chunking_service import ChunkingService, get_chunking_service
from app.services.embedding_service import EmbeddingService, get_embedding_service
from app.services.scanner_service import ScannerService, get_scanner_service
from app.services.vector_store_service import VectorStoreService, get_vector_store_service

logger = get_logger("services.statistics")

# Rough estimate only — NOT tied to any real Gemini billing tier. Configurable
# here in one place so it's trivial to correct once real pricing is wired in.
_ESTIMATED_USD_PER_1K_TOKENS = 0.00015

# "Most asked questions" groups near-duplicate phrasing by a normalized key
# (lowercased, whitespace-collapsed) so "How does auth work?" and "how does
# auth work" count as the same question.
_MAX_TRACKED_QUESTIONS = 200


class UsageMetricsRecorder:
    """Process-wide (class-level) accumulator for AI Chat Engine usage.

    Same in-memory-cache pattern as every pipeline service in this
    codebase (Scanner/Chunking/RAGService's own counters) — resets on
    restart, which is acceptable for Step 12's analytics-only scope.
    """

    _chat_requests: ClassVar[int] = 0
    _total_response_time: ClassVar[float] = 0.0
    _total_retrieval_time: ClassVar[float] = 0.0
    _retrieval_time_samples: ClassVar[int] = 0
    _total_similarity: ClassVar[float] = 0.0
    _similarity_samples: ClassVar[int] = 0
    _prompt_tokens: ClassVar[int] = 0
    _completion_tokens: ClassVar[int] = 0
    _question_counts: ClassVar[Counter] = Counter()
    _repo_chat_requests: ClassVar[Dict[str, int]] = {}
    _repo_response_time: ClassVar[Dict[str, float]] = {}

    @classmethod
    def record_chat_interaction(
        cls,
        repository_name: str,
        question: str,
        processing_time_seconds: float,
        similarity_scores: List[float],
        token_usage: Optional[TokenUsage] = None,
        retrieval_time_seconds: Optional[float] = None,
    ) -> None:
        cls._chat_requests += 1
        cls._total_response_time += processing_time_seconds
        cls._repo_chat_requests[repository_name] = cls._repo_chat_requests.get(repository_name, 0) + 1
        cls._repo_response_time[repository_name] = (
            cls._repo_response_time.get(repository_name, 0.0) + processing_time_seconds
        )

        if retrieval_time_seconds is not None:
            cls._total_retrieval_time += retrieval_time_seconds
            cls._retrieval_time_samples += 1

        for score in similarity_scores:
            cls._total_similarity += score
            cls._similarity_samples += 1

        if token_usage is not None:
            cls._prompt_tokens += token_usage.prompt_tokens
            cls._completion_tokens += token_usage.completion_tokens

        normalized = " ".join(question.strip().lower().split())
        if normalized:
            if len(cls._question_counts) >= _MAX_TRACKED_QUESTIONS and normalized not in cls._question_counts:
                least_common_key, _ = cls._question_counts.most_common()[-1]
                del cls._question_counts[least_common_key]
            cls._question_counts[normalized] += 1

    @classmethod
    def get_insights(cls, repository_name: Optional[str] = None, total_conversations: int = 0) -> AIUsageInsights:
        if repository_name:
            requests = cls._repo_chat_requests.get(repository_name, 0)
            total_time = cls._repo_response_time.get(repository_name, 0.0)
        else:
            requests = cls._chat_requests
            total_time = cls._total_response_time

        avg_response_time = round(total_time / requests, 3) if requests else 0.0
        avg_retrieval_time = (
            round(cls._total_retrieval_time / cls._retrieval_time_samples, 3)
            if cls._retrieval_time_samples
            else 0.0
        )
        avg_similarity = (
            round(cls._total_similarity / cls._similarity_samples, 4) if cls._similarity_samples else 0.0
        )
        total_tokens = cls._prompt_tokens + cls._completion_tokens
        estimated_cost = round((total_tokens / 1000) * _ESTIMATED_USD_PER_1K_TOKENS, 6)

        top_questions = [
            QuestionFrequency(question=q, count=c) for q, c in cls._question_counts.most_common(10)
        ]

        return AIUsageInsights(
            total_chat_requests=requests,
            total_conversations=total_conversations,
            average_response_time_seconds=avg_response_time,
            average_retrieval_time_seconds=avg_retrieval_time,
            average_similarity_score=avg_similarity,
            total_embeddings_generated=0,  # populated by StatisticsService, which knows per-repo totals
            prompt_tokens=cls._prompt_tokens,
            completion_tokens=cls._completion_tokens,
            total_tokens=total_tokens,
            estimated_cost_usd=estimated_cost,
            most_asked_questions=top_questions,
        )


class StatisticsService:
    """Aggregates already-cached Scanner/Chunking/Embedding/VectorStore statistics
    for one repository into a single pipeline-stage view, without re-running any stage."""

    def __init__(
        self,
        scanner_service: ScannerService,
        chunking_service: ChunkingService,
        embedding_service: EmbeddingService,
        vector_store_service: VectorStoreService,
    ) -> None:
        self.scanner_service = scanner_service
        self.chunking_service = chunking_service
        self.embedding_service = embedding_service
        self.vector_store_service = vector_store_service

    async def get_index_status(self, repository_name: str) -> IndexStatus:
        files_indexed = 0
        chunks_created = 0
        embeddings_generated = 0
        vectors_indexed = 0
        last_indexed_at: Optional[datetime] = None
        stage = PipelineStage.CLONED

        try:
            scan_stats = self.scanner_service.get_cached_statistics(repository_name)
            files_indexed = scan_stats.supported_files
            stage = PipelineStage.SCANNED
        except ScanNotPerformedError:
            pass

        try:
            chunk_stats = self.chunking_service.get_cached_statistics(repository_name)
            chunks_created = chunk_stats.chunks_created
            stage = PipelineStage.CHUNKED
        except ChunkingNotPerformedError:
            pass

        try:
            embedding_records = self.embedding_service.get_cached_records(repository_name)
            if embedding_records:
                embeddings_generated = len(embedding_records)
                stage = PipelineStage.EMBEDDED
        except EmbeddingsNotGeneratedError:
            pass

        last_run = self.vector_store_service.get_last_index_run(repository_name)
        if last_run is not None:
            vectors_indexed = last_run.vectors_indexed
            last_indexed_at = last_run.indexed_at
            stage = PipelineStage.INDEXED
        else:
            # Fall back to live ChromaDB collection stats — covers the case
            # where indexing happened in a PRIOR process lifetime (the
            # in-memory `_LAST_INDEX_CACHE` was lost on restart) but the
            # collection itself still exists in persisted ChromaDB storage.
            try:
                vector_stats = await self.vector_store_service.get_statistics(repository_name)
                if vector_stats.total_vectors:
                    vectors_indexed = vector_stats.total_vectors
                    stage = PipelineStage.INDEXED
            except CollectionNotFoundError:
                pass

        progress = self._stage_progress(stage)

        return IndexStatus(
            repository_name=repository_name,
            stage=stage,
            progress_percentage=progress,
            files_indexed=files_indexed,
            chunks_created=chunks_created,
            embeddings_generated=embeddings_generated,
            vectors_indexed=vectors_indexed,
            last_indexed_at=last_indexed_at,
        )

    @staticmethod
    def _stage_progress(stage: PipelineStage) -> float:
        order = [
            PipelineStage.NOT_CLONED,
            PipelineStage.CLONED,
            PipelineStage.SCANNED,
            PipelineStage.CHUNKED,
            PipelineStage.EMBEDDED,
            PipelineStage.INDEXED,
        ]
        return round((order.index(stage) / (len(order) - 1)) * 100, 1)


def get_statistics_service(
    scanner_service: ScannerService = Depends(get_scanner_service),
    chunking_service: ChunkingService = Depends(get_chunking_service),
    embedding_service: EmbeddingService = Depends(get_embedding_service),
    vector_store_service: VectorStoreService = Depends(get_vector_store_service),
) -> StatisticsService:
    """FastAPI dependency provider — see app/api/analytics.py."""
    return StatisticsService(
        scanner_service=scanner_service,
        chunking_service=chunking_service,
        embedding_service=embedding_service,
        vector_store_service=vector_store_service,
    )
