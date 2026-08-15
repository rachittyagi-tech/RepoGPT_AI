"""
app/schemas/chunking.py

Pydantic v2 request/response DTOs for the Code Processing Pipeline
(Step 5). LangChain's `Document` object isn't directly JSON-serializable
in the shape we want for the API, so `ChunkRecord`/`ChunkMetadata` here
are our own DTO mirror of a chunked Document — the service layer converts
between the two at the boundary.
"""

from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Requests
# ---------------------------------------------------------------------------
class ChunkProcessRequest(BaseModel):
    """Body for POST /api/chunking/process"""

    repository_name: str = Field(
        ...,
        description="Repository already scanned via /api/scanner/scan.",
        examples=["psf__requests"],
    )
    chunk_size: Optional[int] = Field(
        default=None,
        ge=100,
        description="Override the default CHUNK_SIZE for this run only (characters per chunk).",
    )
    chunk_overlap: Optional[int] = Field(
        default=None,
        ge=0,
        description="Override the default CHUNK_OVERLAP for this run only.",
    )


# ---------------------------------------------------------------------------
# Chunk metadata / record
# ---------------------------------------------------------------------------
class ChunkMetadata(BaseModel):
    """Metadata attached to every chunk — mirrors a LangChain Document's `.metadata`."""

    repository_name: str
    repository_path: str
    relative_file_path: str
    absolute_file_path: str
    language: str
    extension: str
    file_size: int
    lines_of_code: int
    chunk_number: int = Field(..., description="1-indexed position of this chunk within its file.")
    total_chunks: int = Field(..., description="Total chunks produced from this same file.")


class ChunkRecord(BaseModel):
    """One chunk: its text content plus full metadata."""

    metadata: ChunkMetadata
    content: str
    character_count: int


# ---------------------------------------------------------------------------
# Statistics
# ---------------------------------------------------------------------------
class ChunkStatistics(BaseModel):
    repository_name: str
    processing_time_seconds: float
    total_files: int = Field(..., description="Scanned files considered for processing.")
    files_skipped: int = Field(..., description="Files skipped (empty, unreadable, or errored).")
    documents_created: int = Field(..., description="LangChain Documents created (1 per processed file).")
    chunks_created: int
    average_chunk_size: float
    largest_chunk: int
    smallest_chunk: int
    chunk_size_setting: int
    chunk_overlap_setting: int
    processed_at: datetime


# ---------------------------------------------------------------------------
# Responses
# ---------------------------------------------------------------------------
class ChunkProcessResponse(BaseModel):
    success: bool = True
    message: str
    statistics: ChunkStatistics


class ChunkStatisticsResponse(BaseModel):
    success: bool = True
    statistics: ChunkStatistics


class ChunkListResponse(BaseModel):
    success: bool = True
    repository_name: str
    count: int
    chunks: List[ChunkRecord]
