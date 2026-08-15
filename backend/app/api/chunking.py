"""
app/api/chunking.py

HTTP layer for the Code Processing Pipeline module (Step 5).

Thin router — validates input via Pydantic, delegates to
`ChunkingService`, shapes the response. Error translation (no scanned
files, chunking not yet performed, processing failures) happens via
domain exceptions + the global exception handlers from Step 2.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, status

from app.core.logging import get_logger
from app.schemas.chunking import (
    ChunkListResponse,
    ChunkProcessRequest,
    ChunkProcessResponse,
    ChunkStatisticsResponse,
)
from app.services.chunking_service import ChunkingService, get_chunking_service
from app.middleware.rate_limit import rate_limit

logger = get_logger("api.chunking")

router = APIRouter(tags=["Chunking"], dependencies=[Depends(rate_limit("chunking", 10, 60))])


@router.post(
    "/process",
    response_model=ChunkProcessResponse,
    status_code=status.HTTP_200_OK,
    summary="Convert a scanned repository's files into chunked LangChain Documents",
)
async def process_repository(
    payload: ChunkProcessRequest,
    service: ChunkingService = Depends(get_chunking_service),
) -> ChunkProcessResponse:
    """
    Loads the repository's scanned files (from POST /api/scanner/scan),
    converts each into a LangChain `Document`, and splits them into
    chunks using a syntax-aware splitter where available.

    `chunk_size`/`chunk_overlap` are optional per-request overrides of
    the `CHUNK_SIZE`/`CHUNK_OVERLAP` environment defaults.

    Returns 400 if the repository has no scanned files, 404 if it was
    never scanned at all (implied via scanner cache), 500 on unexpected
    processing failures.
    """
    logger.info("Received chunking request | repo=%s", payload.repository_name)
    statistics = await service.process_repository(
        payload.repository_name,
        chunk_size=payload.chunk_size,
        chunk_overlap=payload.chunk_overlap,
    )
    return ChunkProcessResponse(
        message=f"Processed '{payload.repository_name}' into {statistics.chunks_created} chunks.",
        statistics=statistics,
    )


@router.get(
    "/statistics/{repository}",
    response_model=ChunkStatisticsResponse,
    status_code=status.HTTP_200_OK,
    summary="Get chunking statistics for a processed repository",
)
async def get_chunk_statistics(
    repository: str,
    service: ChunkingService = Depends(get_chunking_service),
) -> ChunkStatisticsResponse:
    """
    Returns processing time, document/chunk counts, and chunk-size
    statistics for `repository`'s last processing run.

    Returns 404 if the repository has never been processed — call
    POST /api/chunking/process first.
    """
    statistics = service.get_cached_statistics(repository)
    return ChunkStatisticsResponse(statistics=statistics)


@router.get(
    "/chunks/{repository}",
    response_model=ChunkListResponse,
    status_code=status.HTTP_200_OK,
    summary="List all chunks produced for a processed repository",
)
async def list_chunks(
    repository: str,
    service: ChunkingService = Depends(get_chunking_service),
) -> ChunkListResponse:
    """
    Returns every chunk (content + metadata) produced by the last
    POST /api/chunking/process call for `repository`.

    Returns 404 if the repository has never been processed.
    """
    chunks = service.get_cached_chunks(repository)
    return ChunkListResponse(repository_name=repository, count=len(chunks), chunks=chunks)
