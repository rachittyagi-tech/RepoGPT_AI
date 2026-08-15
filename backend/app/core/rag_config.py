"""
app/core/rag_config.py

Environment-driven configuration for the RAG Pipeline (Step 8). Same
pattern as `chunk_config.py`, `embedding_config.py`, `vector_config.py`.
"""

from functools import lru_cache

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class RAGSettings(BaseSettings):
    """Strongly-typed, env-overridable settings for retrieval and context building."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ---------------- Retrieval ----------------
    RAG_TOP_K: int = 5
    RAG_MAX_TOP_K: int = 20
    RAG_MIN_SIMILARITY_THRESHOLD: float = 0.3
    """Chunks scoring below this (0-1) are discarded before ranking/context building."""

    # ---------------- Query validation ----------------
    RAG_MIN_QUERY_LENGTH: int = 3
    RAG_MAX_QUERY_LENGTH: int = 500

    # ---------------- Hybrid retrieval (semantic + keyword) ----------------
    RAG_HYBRID_SEMANTIC_WEIGHT: float = 0.7
    RAG_HYBRID_KEYWORD_WEIGHT: float = 0.3
    """Final ranking score = (semantic_weight * similarity) + (keyword_weight *
    keyword_overlap). Pure semantic search alone can miss exact identifier
    matches (e.g. a function name); blending in keyword overlap improves
    recall for code search specifically."""

    # ---------------- Context compression ----------------
    RAG_MAX_CHARS_PER_CHUNK: int = 1500
    """Chunks longer than this are truncated (head + tail kept) before
    being added to the prompt context, to control token spend per chunk."""

    # ---------------- Token / context window management ----------------
    RAG_MAX_CONTEXT_TOKENS: int = 4000
    """Total token budget for the assembled context (chunks + conversation
    history), independent of the LLM's own context window — this keeps the
    RAG layer's output predictable regardless of which model Step 9 uses."""

    RAG_MAX_CONVERSATION_TOKENS: int = 800
    """Portion of the token budget reserved for prior conversation turns."""

    @model_validator(mode="after")
    def validate_weights_and_thresholds(self) -> "RAGSettings":
        if not (0.0 <= self.RAG_MIN_SIMILARITY_THRESHOLD <= 1.0):
            raise ValueError("RAG_MIN_SIMILARITY_THRESHOLD must be between 0 and 1.")
        if round(self.RAG_HYBRID_SEMANTIC_WEIGHT + self.RAG_HYBRID_KEYWORD_WEIGHT, 2) != 1.0:
            raise ValueError("RAG_HYBRID_SEMANTIC_WEIGHT + RAG_HYBRID_KEYWORD_WEIGHT must sum to 1.0.")
        if self.RAG_MIN_QUERY_LENGTH < 1:
            raise ValueError("RAG_MIN_QUERY_LENGTH must be at least 1.")
        if self.RAG_MAX_QUERY_LENGTH <= self.RAG_MIN_QUERY_LENGTH:
            raise ValueError("RAG_MAX_QUERY_LENGTH must be greater than RAG_MIN_QUERY_LENGTH.")
        return self


@lru_cache
def get_rag_settings() -> RAGSettings:
    return RAGSettings()


rag_settings = get_rag_settings()
