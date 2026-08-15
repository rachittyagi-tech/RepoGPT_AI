"""
app/database/vector_repository.py

Low-level CRUD operations against a single ChromaDB collection.

This is the "repository" in Clean Architecture's sense (data-access
layer): it knows how to talk to the storage engine but holds zero
business rules — no dimension validation, no metadata shaping, no error
classification beyond "did the call fail". Those live in
`VectorStoreService`. Every method takes a `Collection` handle obtained
via `ChromaDBClient` — this class never talks to `chromadb` directly at
the client level, only to a collection object.

All methods are synchronous (ChromaDB's client is sync); callers wrap
these in `asyncio.to_thread` — see `VectorStoreService`.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from app.core.exceptions import VectorPersistenceError, VectorSearchFailedError
from app.core.logging import get_logger

logger = get_logger("database.vector_repository")


class VectorRepository:
    """Thin, exception-normalizing CRUD wrapper around one ChromaDB collection."""

    # ------------------------------------------------------------------
    # Writes
    # ------------------------------------------------------------------
    def upsert(
        self,
        collection: Any,
        ids: List[str],
        embeddings: List[List[float]],
        documents: List[str],
        metadatas: List[Dict[str, Any]],
    ) -> None:
        """
        Insert-or-replace by ID. Used for indexing — safe to call
        repeatedly with the same deterministic document IDs (from Step 6)
        without creating duplicates, which is what makes re-indexing a
        repository idempotent.
        """
        try:
            collection.upsert(ids=ids, embeddings=embeddings, documents=documents, metadatas=metadatas)
        except Exception as exc:  # noqa: BLE001
            logger.exception("Upsert failed | collection=%s | count=%d", collection.name, len(ids))
            raise VectorPersistenceError("upsert", reason=str(exc)) from exc

    def update(
        self,
        collection: Any,
        ids: List[str],
        embeddings: Optional[List[List[float]]] = None,
        documents: Optional[List[str]] = None,
        metadatas: Optional[List[Dict[str, Any]]] = None,
    ) -> None:
        """Partial update of existing vectors/content/metadata by ID."""
        try:
            collection.update(ids=ids, embeddings=embeddings, documents=documents, metadatas=metadatas)
        except Exception as exc:  # noqa: BLE001
            logger.exception("Update failed | collection=%s | count=%d", collection.name, len(ids))
            raise VectorPersistenceError("update", reason=str(exc)) from exc

    def delete(
        self,
        collection: Any,
        ids: Optional[List[str]] = None,
        where: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Deletes by explicit ID list and/or a metadata `where` filter."""
        try:
            collection.delete(ids=ids, where=where)
        except Exception as exc:  # noqa: BLE001
            logger.exception("Delete failed | collection=%s", collection.name)
            raise VectorPersistenceError("delete", reason=str(exc)) from exc

    # ------------------------------------------------------------------
    # Reads
    # ------------------------------------------------------------------
    def query(
        self,
        collection: Any,
        query_embedding: List[float],
        top_k: int,
        where: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Similarity search — returns ChromaDB's raw result dict (ids/documents/metadatas/distances)."""
        try:
            return collection.query(
                query_embeddings=[query_embedding],
                n_results=top_k,
                where=where,
                include=["documents", "metadatas", "distances"],
            )
        except Exception as exc:  # noqa: BLE001
            logger.exception("Query failed | collection=%s", collection.name)
            raise VectorSearchFailedError(collection.name, reason=str(exc)) from exc

    def get(
        self,
        collection: Any,
        limit: Optional[int] = None,
        offset: int = 0,
        where: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Direct (non-similarity) fetch — used for statistics and pagination."""
        try:
            return collection.get(limit=limit, offset=offset, where=where, include=["metadatas"])
        except Exception as exc:  # noqa: BLE001
            logger.exception("Get failed | collection=%s", collection.name)
            raise VectorPersistenceError("get", reason=str(exc)) from exc

    def count(self, collection: Any) -> int:
        try:
            return collection.count()
        except Exception as exc:  # noqa: BLE001
            logger.exception("Count failed | collection=%s", collection.name)
            raise VectorPersistenceError("count", reason=str(exc)) from exc
