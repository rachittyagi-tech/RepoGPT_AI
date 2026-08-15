"""
app/api/rag.py

HTTP layer for the RAG Pipeline module (Step 8).

Thin router — validates input via Pydantic, delegates to `RAGService`,
shapes the response. Error translation (invalid query, no relevant
chunks, collection/embedding gaps, token limits) happens via domain
exceptions + the global exception handlers from Step 2.
"""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, status

from app.core.logging import get_logger
from app.schemas.rag import (
    ContextRequest,
    ContextResponse,
    RAGStatisticsResponse,
    RetrievedChunk,
    RetrieveRequest,
    RetrieveResponse,
)
from app.services.rag_service import RAGService, get_rag_service
from app.middleware.rate_limit import rate_limit

logger = get_logger("api.rag")

router = APIRouter(tags=["RAG"], dependencies=[Depends(rate_limit("rag", 20, 60))])


@router.post(
    "/retrieve",
    response_model=RetrieveResponse,
    status_code=status.HTTP_200_OK,
    summary="Retrieve and rank the most relevant chunks for a question (no prompt assembly)",
)
async def retrieve_chunks(
    payload: RetrieveRequest,
    service: RAGService = Depends(get_rag_service),
) -> RetrieveResponse:
    """
    Runs query validation/rewriting, vector search, hybrid ranking,
    duplicate removal, and compression — returns the ranked chunks
    themselves without assembling a final LLM prompt (use
    POST /api/rag/context for that).

    Returns 400 for an invalid question, 404 if the repository isn't
    indexed or nothing clears the similarity threshold.
    """
    logger.info("Received retrieve request | repo=%s", payload.repository_name)
    rewritten_query, chunks = await service.retrieve(
        repository_name=payload.repository_name,
        question=payload.question,
        top_k=payload.top_k,
        score_threshold=payload.score_threshold,
        language=payload.language,
        file_name=payload.file_name,
    )
    return RetrieveResponse(
        repository_name=payload.repository_name,
        question=payload.question,
        rewritten_query=rewritten_query,
        count=len(chunks),
        chunks=chunks,
    )


@router.post(
    "/context",
    response_model=ContextResponse,
    status_code=status.HTTP_200_OK,
    summary="Run the full RAG pipeline and return the final assembled prompt",
)
async def build_context(
    payload: ContextRequest,
    service: RAGService = Depends(get_rag_service),
) -> ContextResponse:
    """
    Runs the complete pipeline end-to-end (retrieve -> rank -> deduplicate
    -> compress -> token-budget -> assemble prompt) and returns the final,
    ready-to-send prompt string alongside its source citations and token
    estimate. Step 9 sends `final_prompt` directly to an LLM.

    Returns 400 for an invalid question or an over-budget question alone,
    404 if the repository isn't indexed or nothing clears the threshold.
    """
    logger.info("Received context request | repo=%s", payload.repository_name)
    rewritten_query, result = await service.build_context(
        repository_name=payload.repository_name,
        question=payload.question,
        top_k=payload.top_k,
        score_threshold=payload.score_threshold,
        language=payload.language,
        file_name=payload.file_name,
        conversation_history=payload.conversation_history,
    )

    return ContextResponse(
        repository_name=payload.repository_name,
        question=payload.question,
        rewritten_query=rewritten_query,
        final_prompt=result.final_prompt,
        context_text=result.context_text,
        sources=result.sources,
        estimated_tokens=result.estimated_tokens,
        chunks_included=result.chunks_included,
        chunks_dropped=result.chunks_dropped,
        generated_at=datetime.now(timezone.utc),
    )


@router.get(
    "/statistics",
    response_model=RAGStatisticsResponse,
    status_code=status.HTTP_200_OK,
    summary="Get cumulative RAG pipeline usage statistics",
)
async def get_statistics(
    service: RAGService = Depends(get_rag_service),
) -> RAGStatisticsResponse:
    """Returns process-wide counters: total retrievals/context builds, averages, last query time."""
    return RAGStatisticsResponse(statistics=service.get_statistics())
