"""
app/database/chromadb_client.py

Thin wrapper around ChromaDB's `PersistentClient` — the ONLY module in
the codebase that imports `chromadb` directly (Dependency Inversion:
everything else — `VectorRepository`, `VectorStoreService` — depends on
this module's interface, never on ChromaDB's API shape directly).

A single client instance lives for the lifetime of the process (module-
level singleton via `get_instance()`), since `PersistentClient` owns a
SQLite file handle at `CHROMA_PERSIST_DIR` — creating multiple clients
pointed at the same directory wastes memory and risks file-lock
contention.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, ClassVar, List, Optional

import chromadb
from chromadb.config import Settings as ChromaClientSettings

from app.core.exceptions import VectorPersistenceError
from app.core.logging import get_logger
from app.core.vector_config import VectorSettings, get_vector_settings

logger = get_logger("database.chromadb_client")


class ChromaDBClient:
    """Process-wide singleton wrapper around a ChromaDB PersistentClient."""

    _instance: ClassVar[Optional["ChromaDBClient"]] = None

    def __init__(self, settings: Optional[VectorSettings] = None) -> None:
        self.settings = settings or get_vector_settings()
        persist_path = Path(self.settings.CHROMA_PERSIST_DIR)
        persist_path.mkdir(parents=True, exist_ok=True)

        try:
            self._client = chromadb.PersistentClient(
                path=str(persist_path.resolve()),
                settings=ChromaClientSettings(anonymized_telemetry=False),
            )
        except Exception as exc:  # noqa: BLE001
            logger.exception("Failed to initialize ChromaDB PersistentClient")
            raise VectorPersistenceError("client initialization", reason=str(exc)) from exc

        logger.info("ChromaDB client initialized | persist_dir=%s", persist_path.resolve())

    @classmethod
    def get_instance(cls) -> "ChromaDBClient":
        """Returns the process-wide singleton, creating it on first use."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @property
    def raw_client(self) -> Any:
        """Escape hatch for advanced use — prefer the methods below where possible."""
        return self._client

    # ------------------------------------------------------------------
    # Collection management
    # ------------------------------------------------------------------
    def get_or_create_collection(self, name: str, dimension: int) -> Any:
        """Idempotent — returns the existing collection if `name` already exists."""
        return self._client.get_or_create_collection(
            name=name,
            metadata={
                "hnsw:space": self.settings.CHROMA_DISTANCE_METRIC,
                "embedding_dimension": dimension,
            },
        )

    def create_collection(self, name: str, dimension: int) -> Any:
        """Strict create — raises (via ChromaDB) if `name` already exists. Caller classifies the error."""
        return self._client.create_collection(
            name=name,
            metadata={
                "hnsw:space": self.settings.CHROMA_DISTANCE_METRIC,
                "embedding_dimension": dimension,
            },
        )

    def get_collection(self, name: str) -> Optional[Any]:
        """Returns the collection handle, or `None` if it doesn't exist."""
        try:
            return self._client.get_collection(name=name)
        except Exception:  # noqa: BLE001 — ChromaDB's "not found" exception type varies by version
            return None

    def collection_exists(self, name: str) -> bool:
        return self.get_collection(name) is not None

    def list_collection_names(self) -> List[str]:
        """
        Returns every collection's name, normalized across ChromaDB
        versions (some return `list[str]`, others `list[Collection]`).
        """
        raw = self._client.list_collections()
        names: List[str] = []
        for item in raw:
            names.append(item if isinstance(item, str) else getattr(item, "name", str(item)))
        return names

    def delete_collection(self, name: str) -> None:
        self._client.delete_collection(name=name)

    @staticmethod
    def get_collection_dimension(collection: Any) -> Optional[int]:
        """Reads back the `embedding_dimension` stored in a collection's metadata at creation time."""
        metadata = getattr(collection, "metadata", None) or {}
        value = metadata.get("embedding_dimension")
        return int(value) if value is not None else None


def get_chromadb_client() -> ChromaDBClient:
    """FastAPI dependency provider — see app/database/vector_repository.py."""
    return ChromaDBClient.get_instance()
