"""
app/core/vector_config.py

Environment-driven configuration for the ChromaDB Vector Store Layer
(Step 7). Kept as its own `BaseSettings`, same pattern as
`chunk_config.py` and `embedding_config.py`.
"""

from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict

DistanceMetric = Literal["cosine", "l2", "ip"]


class VectorSettings(BaseSettings):
    """Strongly-typed, env-overridable settings for the vector store."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ---------------- Persistence ----------------
    CHROMA_PERSIST_DIR: str = "data/chroma_db"
    """Directory ChromaDB writes its SQLite + HNSW index files to. Relative
    to the backend working directory, mirroring REPOSITORIES_BASE_DIR."""

    # ---------------- Collection naming / repository isolation ----------------
    COLLECTION_NAME_PREFIX: str = "repogpt_"
    """Every repository gets its own collection, named
    f"{COLLECTION_NAME_PREFIX}{sanitized_repository_name}" — this is what
    gives repository isolation: one repo's vectors can never leak into
    another repo's search results, and deleting a repository's data is
    just deleting one collection."""

    # ---------------- Distance metric ----------------
    CHROMA_DISTANCE_METRIC: DistanceMetric = "cosine"
    """'cosine' is the standard choice for sentence-embedding similarity
    (magnitude-invariant); 'l2' (Euclidean) and 'ip' (inner product) are
    supported for providers/models that are tuned for them."""

    # ---------------- Search defaults ----------------
    DEFAULT_TOP_K: int = 5
    MAX_TOP_K: int = 50
    DEFAULT_SCORE_THRESHOLD: float = 0.0
    """Minimum similarity score (0-1, higher = more similar) for a result
    to be included when the caller doesn't specify their own threshold."""

    # ---------------- Batch sizing ----------------
    BATCH_UPSERT_SIZE: int = 200
    """ChromaDB writes are chunked into batches of this size — protects
    against a single oversized `add()` call for very large repositories."""


@lru_cache
def get_vector_settings() -> VectorSettings:
    return VectorSettings()


vector_settings = get_vector_settings()
