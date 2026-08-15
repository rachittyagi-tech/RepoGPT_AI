"""
app/schemas/rag.py

Pydantic v2 request/response DTOs for the RAG Pipeline (Step 8).
"""

from __future__ import annotations

from datetime import datetime
from typing import List, Literal, Optional

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Shared building blocks
# ---------------------------------------------------------------------------
class ConversationTurn(BaseModel):
    """One prior turn in the conversation, used for conversation-aware context."""

    role: Literal["user", "assistant"]
    content: str


class SourceReference(BaseModel):
    """A citation back to the exact file/chunk a piece of context came from."""

    repository_name: str
    file_path: str
    language: str
    chunk_number: int
    total_chunks: int
    score: float


class RetrievedChunk(BaseModel):
    """One retrieved chunk with its content, score, and location metadata."""

    document_id: str
    content: str
    score: float = Field(..., description="Final ranking score (0-1), hybrid semantic + keyword.")
    similarity_score: float = Field(..., description="Raw vector similarity score before hybrid ranking.")
    repository_name: str
    file_path: str
    language: str
    extension: str
    chunk_number: int
    total_chunks: int
    lines_of_code: int


# ---------------------------------------------------------------------------
# POST /api/rag/retrieve
# ---------------------------------------------------------------------------
class RetrieveRequest(BaseModel):
    repository_name: str = Field(..., examples=["psf__requests"])
    question: str = Field(..., examples=["How does session authentication work?"])
    top_k: Optional[int] = Field(default=None, ge=1)
    score_threshold: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    language: Optional[str] = Field(default=None, description="Filter to one programming language.")
    file_name: Optional[str] = Field(default=None, description="Filter to one file name.")


class RetrieveResponse(BaseModel):
    success: bool = True
    repository_name: str
    question: str
    rewritten_query: str
    count: int
    chunks: List[RetrievedChunk]


# ---------------------------------------------------------------------------
# POST /api/rag/context
# ---------------------------------------------------------------------------
class ContextRequest(BaseModel):
    repository_name: str = Field(..., examples=["psf__requests"])
    question: str = Field(..., examples=["Explain how the Session class handles retries."])
    top_k: Optional[int] = Field(default=None, ge=1)
    score_threshold: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    language: Optional[str] = None
    file_name: Optional[str] = None
    conversation_history: Optional[List[ConversationTurn]] = Field(
        default=None, description="Prior turns, oldest first, for conversation-aware context."
    )


class ContextResponse(BaseModel):
    success: bool = True
    repository_name: str
    question: str
    rewritten_query: str
    final_prompt: str = Field(..., description="The fully assembled prompt, ready to send to an LLM in Step 9.")
    context_text: str = Field(..., description="Just the retrieved-context portion, without the prompt scaffolding.")
    sources: List[SourceReference]
    estimated_tokens: int
    chunks_included: int
    chunks_dropped: int = Field(..., description="Retrieved chunks excluded due to the token budget.")
    generated_at: datetime


# ---------------------------------------------------------------------------
# GET /api/rag/statistics
# ---------------------------------------------------------------------------
class RAGStatistics(BaseModel):
    total_retrievals: int
    total_context_builds: int
    average_chunks_retrieved: float
    average_estimated_tokens: float
    last_query_at: Optional[datetime] = None


class RAGStatisticsResponse(BaseModel):
    success: bool = True
    statistics: RAGStatistics
