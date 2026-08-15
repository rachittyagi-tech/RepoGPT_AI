"""
app/schemas/vector_store.py

Pydantic v2 request/response DTOs for the ChromaDB Vector Store Layer
(Step 7).
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, model_validator


# ---------------------------------------------------------------------------
# Metadata — the exact fields required by the Step 7 spec
# ---------------------------------------------------------------------------
class VectorMetadata(BaseModel):
    repository_name: str
    repository_id: str
    file_name: str
    relative_path: str
    language: str
    extension: str
    chunk_number: int
    total_chunks: int
    lines_of_code: int
    timestamp: datetime


# ---------------------------------------------------------------------------
# Index (insert) — POST /api/vector/index
# ---------------------------------------------------------------------------
class IndexRequest(BaseModel):
    repository_name: str = Field(
        ...,
        description="Repository already embedded via /api/embeddings/generate.",
        examples=["psf__requests"],
    )
    force_recreate: bool = Field(
        default=False,
        description="If true, deletes and recreates the collection before indexing (fresh start).",
    )


class IndexStatistics(BaseModel):
    repository_name: str
    collection_name: str
    vectors_indexed: int
    vectors_failed: int
    dimension: int
    distance_metric: str
    processing_time_seconds: float
    indexed_at: datetime


class IndexResponse(BaseModel):
    success: bool = True
    message: str
    statistics: IndexStatistics


# ---------------------------------------------------------------------------
# Search — POST /api/vector/search
# ---------------------------------------------------------------------------
class SearchRequest(BaseModel):
    repository_name: str = Field(..., description="Which repository's collection to search.")
    query_text: Optional[str] = Field(
        default=None, description="Raw text query — embedded on the fly using the configured provider."
    )
    query_embedding: Optional[List[float]] = Field(
        default=None, description="Pre-computed query vector (alternative to query_text)."
    )
    top_k: int = Field(default=5, ge=1, description="Number of results to return.")
    score_threshold: Optional[float] = Field(
        default=None, ge=0.0, le=1.0, description="Minimum similarity score (0-1) for a result to be kept."
    )
    language: Optional[str] = Field(default=None, description="Filter results to one language, e.g. 'Python'.")
    file_name: Optional[str] = Field(default=None, description="Filter results to one file name.")
    metadata_filters: Optional[Dict[str, Any]] = Field(
        default=None, description="Advanced raw ChromaDB 'where' filter, merged with language/file_name."
    )

    @model_validator(mode="after")
    def validate_query_source(self) -> "SearchRequest":
        if not self.query_text and not self.query_embedding:
            raise ValueError("Provide either 'query_text' or 'query_embedding'.")
        if self.query_text and self.query_embedding:
            raise ValueError("Provide only one of 'query_text' or 'query_embedding', not both.")
        return self


class SearchResult(BaseModel):
    document_id: str
    content: str
    metadata: VectorMetadata
    score: float = Field(..., description="Similarity score, 0-1, higher = more similar.")
    distance: float = Field(..., description="Raw ChromaDB distance value (metric-dependent).")


class SearchResponse(BaseModel):
    success: bool = True
    repository_name: str
    query_text: Optional[str] = None
    count: int
    results: List[SearchResult]


# ---------------------------------------------------------------------------
# Update — PUT /api/vector/update
# ---------------------------------------------------------------------------
class VectorUpdateItem(BaseModel):
    document_id: str
    content: Optional[str] = None
    embedding: Optional[List[float]] = None
    metadata: Optional[Dict[str, Any]] = None

    @model_validator(mode="after")
    def validate_at_least_one_field(self) -> "VectorUpdateItem":
        if self.content is None and self.embedding is None and self.metadata is None:
            raise ValueError("Provide at least one of 'content', 'embedding', or 'metadata' to update.")
        return self


class UpdateRequest(BaseModel):
    repository_name: str
    updates: List[VectorUpdateItem] = Field(..., min_length=1)


class UpdateResponse(BaseModel):
    success: bool = True
    message: str
    updated_count: int


# ---------------------------------------------------------------------------
# Delete — DELETE /api/vector/delete
# ---------------------------------------------------------------------------
class DeleteRequest(BaseModel):
    repository_name: str
    document_ids: Optional[List[str]] = Field(default=None, description="Delete these specific chunk IDs.")
    file_name: Optional[str] = Field(default=None, description="Delete every chunk belonging to this file.")
    delete_all: bool = Field(default=False, description="Delete every vector in the repository's collection.")

    @model_validator(mode="after")
    def validate_target(self) -> "DeleteRequest":
        if not self.document_ids and not self.file_name and not self.delete_all:
            raise ValueError("Provide 'document_ids', 'file_name', or set 'delete_all' to True.")
        return self


class DeleteResponse(BaseModel):
    success: bool = True
    message: str
    deleted_count: int


# ---------------------------------------------------------------------------
# Collections — GET /api/vector/collections, DELETE /api/vector/collection/{name}
# ---------------------------------------------------------------------------
class CollectionInfo(BaseModel):
    collection_name: str
    repository_name: str
    vector_count: int
    dimension: Optional[int] = None
    distance_metric: Optional[str] = None


class CollectionsResponse(BaseModel):
    success: bool = True
    count: int
    collections: List[CollectionInfo]


class DeleteCollectionResponse(BaseModel):
    success: bool = True
    message: str
    collection_name: str


# ---------------------------------------------------------------------------
# Statistics — GET /api/vector/statistics
# ---------------------------------------------------------------------------
class VectorStatistics(BaseModel):
    repository_name: str
    collection_name: str
    total_vectors: int
    dimension: Optional[int] = None
    distance_metric: Optional[str] = None
    language_counts: Dict[str, int]
    unique_files: int


class StatisticsResponse(BaseModel):
    success: bool = True
    statistics: VectorStatistics
