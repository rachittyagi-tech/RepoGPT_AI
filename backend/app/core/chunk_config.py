"""
app/core/chunk_config.py

Environment-driven configuration for the Code Processing Pipeline
(Step 5) — chunk size, overlap, separators, and safety limits.

Kept as its own Pydantic `BaseSettings` (separate from `app/core/settings.py`)
because these values are specific to the chunking/RAG-prep domain and will
likely be tuned independently of general app config as the RAG pipeline
matures in later steps — Single Responsibility applies at the config level
too, not just in code.
"""

from functools import lru_cache
from typing import List

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class ChunkSettings(BaseSettings):
    """
    Strongly-typed, env-overridable settings for text/code splitting.
    All fields are prefixed with `CHUNK_` in the environment, e.g.
    `CHUNK_SIZE=1500` in `.env` overrides `CHUNK_SIZE` below.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_prefix="CHUNK_",
        case_sensitive=False,
        extra="ignore",
    )

    # ---------------- Core splitter parameters ----------------
    SIZE: int = 1000
    """Target maximum characters per chunk."""

    OVERLAP: int = 200
    """Characters of overlap between consecutive chunks (preserves context across boundaries)."""

    # ---------------- Safety limits ----------------
    MAX_CHUNKS_PER_FILE: int = 500
    """Hard ceiling on chunks produced from a single file — guards against
    pathological inputs (e.g. a minified 10MB JSON file) blowing up memory."""

    MAX_CHUNKS_PER_REPOSITORY: int = 50_000
    """Hard ceiling on total chunks produced by one /process call."""

    # ---------------- Fallback separators (generic / non-code files) ----------------
    DEFAULT_SEPARATORS: List[str] = ["\n\n", "\n", " ", ""]

    @field_validator("SIZE")
    @classmethod
    def validate_size(cls, v: int) -> int:
        if v < 100:
            raise ValueError("CHUNK_SIZE must be at least 100 characters.")
        return v

    @field_validator("OVERLAP")
    @classmethod
    def validate_overlap(cls, v: int) -> int:
        if v < 0:
            raise ValueError("CHUNK_OVERLAP cannot be negative.")
        return v

    @model_validator(mode="after")
    def validate_overlap_smaller_than_size(self) -> "ChunkSettings":
        if self.OVERLAP >= self.SIZE:
            raise ValueError(
                f"CHUNK_OVERLAP ({self.OVERLAP}) must be smaller than CHUNK_SIZE ({self.SIZE})."
            )
        return self


@lru_cache
def get_chunk_settings() -> ChunkSettings:
    """Cached accessor — mirrors `get_settings()` in app/core/settings.py."""
    return ChunkSettings()


chunk_settings = get_chunk_settings()
