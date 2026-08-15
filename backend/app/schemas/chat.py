"""
app/schemas/chat.py

Pydantic v2 request/response DTOs for the AI Chat Engine (Step 9).
Reuses `SourceReference` from Step 8's RAG schemas (DRY — a chat
citation IS a RAG source reference, unchanged).
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field

from app.schemas.rag import SourceReference


class ChatRole(str, Enum):
    USER = "user"
    ASSISTANT = "assistant"


class ChatMessage(BaseModel):
    """One message in a conversation's history."""

    role: ChatRole
    content: str
    timestamp: datetime
    sources: List[SourceReference] = Field(default_factory=list)


class TokenUsage(BaseModel):
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int


# ---------------------------------------------------------------------------
# POST /api/chat, POST /api/chat/stream
# ---------------------------------------------------------------------------
class ChatRequest(BaseModel):
    repository_name: str = Field(..., examples=["psf__requests"])
    message: str = Field(..., examples=["How does the Session class handle retries?"])
    conversation_id: Optional[str] = Field(
        default=None,
        description="Omit to start a new conversation; provide to continue an existing one.",
    )
    top_k: Optional[int] = Field(default=None, ge=1)
    score_threshold: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    language: Optional[str] = None
    file_name: Optional[str] = None


class ChatResponse(BaseModel):
    success: bool = True
    answer: str
    repository_name: str
    conversation_id: str
    processing_time_seconds: float
    token_usage: TokenUsage
    sources: List[SourceReference]
    similarity_scores: List[float]
    created_at: datetime


# ---------------------------------------------------------------------------
# GET /api/chat/history, DELETE /api/chat/history
# ---------------------------------------------------------------------------
class HistoryResponse(BaseModel):
    success: bool = True
    conversation_id: str
    repository_name: str
    messages: List[ChatMessage]
    message_count: int


class ClearHistoryResponse(BaseModel):
    success: bool = True
    message: str
    conversation_id: str


# ---------------------------------------------------------------------------
# GET /api/chat/models
# ---------------------------------------------------------------------------
class ModelInfo(BaseModel):
    name: str
    display_name: str
    max_output_tokens: int
    status: str = Field(..., description="'active' or 'not_configured'.")


class ModelsResponse(BaseModel):
    success: bool = True
    active_model: str
    models: List[ModelInfo]
