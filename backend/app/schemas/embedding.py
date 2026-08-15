"""
app/schemas/embedding.py

Pydantic v2 request/response DTOs for the Embedding Generation Layer
(Step 6). Reuses `ChunkMetadata` from Step 5 rather than redefining an
identical metadata shape (DRY) — an embedding's metadata IS the chunk's
metadata, unchanged.
"""

from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field

from app.schemas.chunking import ChunkMetadata


# ---------------------------------------------------------------------------
# Requests
# ---------------------------------------------------------------------------
class EmbeddingGenerateRequest(BaseModel):
    """Body for POST /api/embeddings/generate"""

    repository_name: str = Field(
        ...,
        description="Repository already processed via /api/chunking/process.",
        examples=["psf__requests"],
    )
    provider: Optional[str] = Field(
        default=None,
        description="Override the default EMBEDDING_PROVIDER for this call only ('gemini' or 'huggingface').",
    )
    batch_size: Optional[int] = Field(
        default=None,
        ge=1,
        description="Override the default BATCH_SIZE for this call only.",
    )
    include_vectors: bool = Field(
        default=True,
        description="Include full embedding vectors in the response (set False for a lighter payload).",
    )


# ---------------------------------------------------------------------------
# Per-document embedding record
# ---------------------------------------------------------------------------
class EmbeddingRecord(BaseModel):
    """One chunk's embedding — vector, metadata, timing, and a stable ID."""

    document_id: str = Field(..., description="Deterministic ID derived from repo + file + chunk number.")
    embedding: List[float] = Field(default_factory=list)
    metadata: ChunkMetadata
    processing_time_seconds: float
    dimension: int


# ---------------------------------------------------------------------------
# Statistics
# ---------------------------------------------------------------------------
class EmbeddingStatistics(BaseModel):
    repository_name: str
    provider: str
    model: str
    dimension: int
    total_documents: int = Field(..., description="Chunks considered for embedding.")
    embeddings_created: int
    embeddings_failed: int
    batches_processed: int
    batch_size: int
    total_processing_time_seconds: float
    average_time_per_document_seconds: float
    generated_at: datetime


# ---------------------------------------------------------------------------
# Responses
# ---------------------------------------------------------------------------
class EmbeddingGenerateResponse(BaseModel):
    success: bool = True
    message: str
    statistics: EmbeddingStatistics
    records: List[EmbeddingRecord]


class ProviderInfo(BaseModel):
    name: str
    display_name: str
    status: str = Field(..., description="'available', 'not_configured', or 'planned'.")
    model: Optional[str] = None
    dimension: Optional[int] = None
    requires_api_key: bool = False
    notes: Optional[str] = None


class ProvidersResponse(BaseModel):
    success: bool = True
    active_provider: str
    providers: List[ProviderInfo]


class EmbeddingStatusResponse(BaseModel):
    success: bool = True
    active_provider: str
    is_configured: bool
    model: str
    dimension: Optional[int] = None
    batch_size: int
    max_retries: int
    timeout_seconds: int
    last_run: Optional[EmbeddingStatistics] = None
