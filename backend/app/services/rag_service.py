"""
app/services/rag_service.py

Orchestrates the full RAG pipeline (Step 8):

    Query Validation -> Query Rewriting -> Vector Search (ChromaDB) ->
    Metadata Filtering -> Similarity Ranking -> Context Compression ->
    Duplicate Removal -> Prompt Context Builder -> Return Final Context

This class owns the pipeline's ORDER of stages only; each stage's actual
logic lives in its own single-responsibility service (`QueryRewriter`,
`RetrieverService`, `ContextRanker`, `ContextBuilder`) — this class never
duplicates their logic, only sequences it (Single Responsibility +
Dependency Inversion: RAGService depends on 4 small interfaces, not on
ChromaDB/embedding/chunking internals directly).
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import ClassVar, List, Optional, Tuple

from fastapi import Depends

from app.core.exceptions import NoRelevantChunksError
from app.core.logging import get_logger
from app.core.rag_config import RAGSettings, get_rag_settings
from app.schemas.rag import ConversationTurn, RAGStatistics, RetrievedChunk
from app.services.context_builder import ContextBuilder, ContextBuildResult, get_context_builder
from app.services.context_ranker import ContextRanker, get_context_ranker
from app.services.query_rewriter import QueryRewriter, get_query_rewriter
from app.services.retriever_service import RetrieverService, get_retriever_service

logger = get_logger("services.rag")


class RAGService:
    """Orchestrates query rewriting, retrieval, ranking, and context building."""

    # Simple in-memory usage counters — backs GET /api/rag/statistics.
    _total_retrievals: ClassVar[int] = 0
    _total_context_builds: ClassVar[int] = 0
    _total_chunks_retrieved: ClassVar[int] = 0
    _total_estimated_tokens: ClassVar[int] = 0
    _last_query_at: ClassVar[Optional[datetime]] = None

    def __init__(
        self,
        query_rewriter: QueryRewriter,
        retriever_service: RetrieverService,
        context_ranker: ContextRanker,
        context_builder: ContextBuilder,
        settings: Optional[RAGSettings] = None,
    ) -> None:
        self.query_rewriter = query_rewriter
        self.retriever_service = retriever_service
        self.context_ranker = context_ranker
        self.context_builder = context_builder
        self.settings = settings or get_rag_settings()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    async def retrieve(
        self,
        repository_name: str,
        question: str,
        top_k: Optional[int] = None,
        score_threshold: Optional[float] = None,
        language: Optional[str] = None,
        file_name: Optional[str] = None,
    ) -> Tuple[str, List[RetrievedChunk]]:
        """
        Runs Query Validation -> Query Rewriting -> Vector Search ->
        Metadata Filtering -> Similarity Ranking -> Duplicate Removal ->
        Context Compression, returning `(rewritten_query, ranked_chunks)`.

        Used directly by POST /api/rag/retrieve, and as the first half of
        `build_context` for POST /api/rag/context.

        Raises:
            InvalidQueryError: question fails validation.
            CollectionNotFoundError / EmptyCollectionError: propagated
                from Step 7 if the repository isn't indexed / has no vectors.
            NoRelevantChunksError: search succeeded but nothing cleared
                the similarity threshold.
        """
        validated_question = self.query_rewriter.validate(question)
        rewritten_query = self.query_rewriter.rewrite(validated_question, language=language)
        keywords = self.query_rewriter.extract_keywords(validated_question)

        effective_top_k = min(top_k or self.settings.RAG_TOP_K, self.settings.RAG_MAX_TOP_K)
        effective_threshold = (
            score_threshold
            if score_threshold is not None
            else self.settings.RAG_MIN_SIMILARITY_THRESHOLD
        )

        chunks = await self.retriever_service.retrieve(
            repository_name=repository_name,
            query_text=rewritten_query,
            top_k=effective_top_k,
            score_threshold=effective_threshold,
            language=language,
            file_name=file_name,
        )

        if not chunks:
            raise NoRelevantChunksError(repository_name, effective_threshold)

        ranked = self.context_ranker.rank(chunks, keywords)
        deduplicated = self.context_ranker.deduplicate(ranked)
        compressed = self.context_ranker.compress(deduplicated)

        self._record_retrieval(len(compressed))
        logger.info(
            "Retrieval complete | repo=%s | question=%r | chunks=%d",
            repository_name,
            validated_question,
            len(compressed),
        )
        return rewritten_query, compressed

    async def build_context(
        self,
        repository_name: str,
        question: str,
        top_k: Optional[int] = None,
        score_threshold: Optional[float] = None,
        language: Optional[str] = None,
        file_name: Optional[str] = None,
        conversation_history: Optional[List[ConversationTurn]] = None,
    ) -> Tuple[str, ContextBuildResult]:
        """
        Runs the full pipeline end-to-end and returns
        `(rewritten_query, ContextBuildResult)` — the latter holding the
        final prompt, ready for Step 9 to send to an LLM.
        """
        rewritten_query, chunks = await self.retrieve(
            repository_name, question, top_k, score_threshold, language, file_name
        )

        result = self.context_builder.build(
            question=question, chunks=chunks, conversation_history=conversation_history
        )

        self._record_context_build(result.estimated_tokens)
        logger.info(
            "Context build complete | repo=%s | chunks_included=%d | chunks_dropped=%d | tokens=%d",
            repository_name,
            result.chunks_included,
            result.chunks_dropped,
            result.estimated_tokens,
        )
        return rewritten_query, result

    def get_statistics(self) -> RAGStatistics:
        avg_chunks = (
            round(self._total_chunks_retrieved / self._total_retrievals, 2)
            if self._total_retrievals
            else 0.0
        )
        avg_tokens = (
            round(self._total_estimated_tokens / self._total_context_builds, 2)
            if self._total_context_builds
            else 0.0
        )
        return RAGStatistics(
            total_retrievals=self._total_retrievals,
            total_context_builds=self._total_context_builds,
            average_chunks_retrieved=avg_chunks,
            average_estimated_tokens=avg_tokens,
            last_query_at=self._last_query_at,
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    @classmethod
    def _record_retrieval(cls, chunk_count: int) -> None:
        cls._total_retrievals += 1
        cls._total_chunks_retrieved += chunk_count
        cls._last_query_at = datetime.now(timezone.utc)

    @classmethod
    def _record_context_build(cls, estimated_tokens: int) -> None:
        cls._total_context_builds += 1
        cls._total_estimated_tokens += estimated_tokens


def get_rag_service(
    query_rewriter: QueryRewriter = Depends(get_query_rewriter),
    retriever_service: RetrieverService = Depends(get_retriever_service),
    context_ranker: ContextRanker = Depends(get_context_ranker),
    context_builder: ContextBuilder = Depends(get_context_builder),
) -> RAGService:
    """FastAPI dependency provider — see app/api/rag.py."""
    return RAGService(
        query_rewriter=query_rewriter,
        retriever_service=retriever_service,
        context_ranker=context_ranker,
        context_builder=context_builder,
    )
