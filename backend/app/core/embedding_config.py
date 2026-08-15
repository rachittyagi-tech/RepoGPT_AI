"""
app/core/embedding_config.py

Environment-driven configuration for the Embedding Generation Layer
(Step 6). Kept as its own `BaseSettings` (like `chunk_config.py`) since
these values evolve independently of general app config as more
providers are added.
"""

from functools import lru_cache
from typing import Literal, Optional

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Providers implemented today. The architecture (see app/providers/) is
# built so adding "openai" | "voyage" | "jina" | "azure_openai" later is
# just: (1) add a new provider class implementing BaseEmbeddingProvider,
# (2) add one line to the factory in embedding_service.py, (3) add the
# name here. No existing code changes.
EmbeddingProviderName = Literal["gemini", "huggingface"]


class EmbeddingSettings(BaseSettings):
    """Strongly-typed, env-overridable settings for embedding generation."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ---------------- Provider selection ----------------
    EMBEDDING_PROVIDER: EmbeddingProviderName = "huggingface"
    """Which provider to use by default. HuggingFace is the default since
    it runs locally and needs no API key — good out-of-the-box dev experience."""

    # ---------------- Gemini ----------------
    GEMINI_API_KEY: Optional[str] = None
    GEMINI_EMBEDDING_MODEL: str = "text-embedding-004"

    # ---------------- HuggingFace ----------------
    HUGGINGFACE_MODEL: str = "sentence-transformers/all-MiniLM-L6-v2"

    # ---------------- Shared batch/retry/timeout behavior ----------------
    BATCH_SIZE: int = 32
    MAX_RETRIES: int = Field(default=3, validation_alias="EMBEDDING_MAX_RETRIES")
    """Step 14 fix: was previously read from a plain `MAX_RETRIES` env var —
    which `GeminiChatSettings.MAX_RETRIES` (app/core/gemini_config.py) ALSO
    read from, so setting one in `.env` silently overrode the other. Now a
    distinct `EMBEDDING_MAX_RETRIES` env var, still exposed as `.MAX_RETRIES`
    on this settings object so no call site needs to change."""
    TIMEOUT: int = 30
    """Per-batch timeout in seconds, enforced via asyncio.wait_for regardless
    of provider — keeps this cross-cutting concern out of every provider class."""

    @model_validator(mode="after")
    def validate_positive_values(self) -> "EmbeddingSettings":
        if self.BATCH_SIZE < 1:
            raise ValueError("BATCH_SIZE must be at least 1.")
        if self.MAX_RETRIES < 0:
            raise ValueError("MAX_RETRIES cannot be negative.")
        if self.TIMEOUT < 1:
            raise ValueError("TIMEOUT must be at least 1 second.")
        return self


@lru_cache
def get_embedding_settings() -> EmbeddingSettings:
    return EmbeddingSettings()


embedding_settings = get_embedding_settings()
