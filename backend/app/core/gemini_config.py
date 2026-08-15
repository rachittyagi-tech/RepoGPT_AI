"""
app/core/gemini_config.py

Environment-driven configuration for the AI Chat Engine (Step 9). Same
pattern as `embedding_config.py`/`rag_config.py`. Kept separate from
`embedding_config.py` even though both talk to Gemini — one configures
embedding generation, this one configures chat/generation behavior
(temperature, sampling, output length), which are independent concerns
that evolve on their own schedules.
"""

from functools import lru_cache
from typing import Optional

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class GeminiChatSettings(BaseSettings):
    """Strongly-typed, env-overridable settings for Gemini-powered chat."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    GEMINI_API_KEY: Optional[str] = None
    GEMINI_MODEL: str = "gemini-1.5-flash"
    MAX_OUTPUT_TOKENS: int = 2048
    TEMPERATURE: float = 0.3
    """Low-ish default (0.3) — chat answers should be grounded and consistent,
    not creative, since the system prompt forbids hallucination."""
    TOP_P: float = 0.95
    TOP_K: int = 40
    REQUEST_TIMEOUT: int = 60
    """Per-attempt timeout in seconds, enforced via asyncio.wait_for."""

    MAX_RETRIES: int = Field(default=2, validation_alias="GEMINI_CHAT_MAX_RETRIES")
    """Step 14 fix: was previously read from a plain `MAX_RETRIES` env var,
    the same one `EmbeddingSettings.MAX_RETRIES` (app/core/embedding_config.py)
    read from — setting one in `.env` silently overrode the other. Now a
    distinct `GEMINI_CHAT_MAX_RETRIES` env var; still `.MAX_RETRIES` here."""

    @model_validator(mode="after")
    def validate_ranges(self) -> "GeminiChatSettings":
        if not (0.0 <= self.TEMPERATURE <= 2.0):
            raise ValueError("TEMPERATURE must be between 0.0 and 2.0.")
        if not (0.0 <= self.TOP_P <= 1.0):
            raise ValueError("TOP_P must be between 0.0 and 1.0.")
        if self.TOP_K < 1:
            raise ValueError("TOP_K must be at least 1.")
        if self.MAX_OUTPUT_TOKENS < 1:
            raise ValueError("MAX_OUTPUT_TOKENS must be at least 1.")
        if self.REQUEST_TIMEOUT < 1:
            raise ValueError("REQUEST_TIMEOUT must be at least 1 second.")
        if self.MAX_RETRIES < 0:
            raise ValueError("MAX_RETRIES cannot be negative.")
        return self


@lru_cache
def get_gemini_chat_settings() -> GeminiChatSettings:
    return GeminiChatSettings()


gemini_chat_settings = get_gemini_chat_settings()
