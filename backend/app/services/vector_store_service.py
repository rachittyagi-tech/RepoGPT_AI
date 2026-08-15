"""
app/services/vector_store_service.py

Business logic for the ChromaDB Vector Store Layer (Step 7).

Responsibilities:
    - Repository isolation: every GitHub repository gets its own ChromaDB
      collection (f"{COLLECTION_NAME_PREFIX}{repository_name}") — one
      repo's vectors can never appear in another repo's search results,
      and deleting a repository's data is just deleting one collection
    - Indexing: pulls Step 6's cached embedding records, validates
      dimensions, batches upserts (idempotent — safe to re-run)
    - Similarity search: embeds a raw query on the fly (reusing Step 6's
      EmbeddingService) or accepts a pre-computed vector, applies
      metadata filters, converts ChromaDB distances to a 0-1 similarity
      score, applies an optional score threshold
    - Update / delete (single or batch) by document ID or metadata filter
    - Collection management + aggregate statistics

Clean Architecture note: this is the ONLY layer that knows about the
domain rules (dimension validation, metadata shaping, error
classification). `VectorRepository` (data access) and `ChromaDBClient`
(connection management) below it know nothing about repositories, chunks,
or embeddings — they operate on generic ids/vectors/documents/metadata.
"""

from __future__ import annotations

import asyncio
import hashlib
import re
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, ClassVar, Dict, List, Optional, Tuple

from fastapi import Depends

from app.core.exceptions import (
    CollectionNotFoundError,
    DimensionMismatchError,
    EmptyCollectionError,
)
from app.core.logging import get_logger
from app.core.vector_config import VectorSettings, get_vector_settings
from app.database.chromadb_client import ChromaDBClient, get_chromadb_client
from app.database.vector_repository import VectorRepository
from app.schemas.embedding import EmbeddingRecord
from app.schemas.vector_store import (
    CollectionInfo,
    IndexStatistics,
    SearchResult,
    VectorMetadata,
    VectorStatistics,
)
from app.services.embedding_service import EmbeddingService, get_embedding_service

logger = get_logger("services.vector_store")

_INVALID_COLLECTION_CHARS = re.compile(r"[^a-zA-Z0-9._-]")


class VectorStoreService:
    """Orchestrates ChromaDB-backed storage, search, and lifecycle for repository vectors."""

    # Last successful index run per repository — read-only lookup for the
    # Analytics module (Step 12: "Last Indexed Time" / index status).
    # Same in-memory, class-level cache pattern used by every other
    # pipeline service (Scanner/Chunking/Embedding) — not persisted across
    # restarts, which is fine since a restart also clears ChromaDB's
    # in-process client state consumers care about here.
    _LAST_INDEX_CACHE: ClassVar[Dict[str, IndexStatistics]] = {}

    def __init__(
        self,
        chromadb_client: ChromaDBClient,
        embedding_service: EmbeddingService,
        settings: Optional[VectorSettings] = None,
    ) -> None:
        self.client = chromadb_client
        self.embedding_service = embedding_service
        self.settings = settings or get_vector_settings()
        self.repo = VectorRepository()

    # ------------------------------------------------------------------
    # Indexing
    # ------------------------------------------------------------------
    async def index_repository(self, repository_name: str, force_recreate: bool = False) -> IndexStatistics:
        """
        Indexes every cached embedding record (from Step 6) for
        `repository_name` into its dedicated ChromaDB collection.

        Idempotent: re-running with the same repository upserts by the
        same deterministic document IDs rather than duplicating vectors.
        """
        start_time = time.perf_counter()
        records = self.embedding_service.get_cached_records(repository_name)

        valid_records, invalid_count = self._validate_records(records)
        dimension = len(valid_records[0].embedding) if valid_records else 0

        collection_name = self._build_collection_name(repository_name)

        if force_recreate and await asyncio.to_thread(self.client.collection_exists, collection_name):
            logger.info("force_recreate=True — dropping existing collection %s", collection_name)
            await asyncio.to_thread(self.client.delete_collection, collection_name)

        collection = await asyncio.to_thread(
            self.client.get_or_create_collection, collection_name, dimension
        )

        stored_dimension = self.client.get_collection_dimension(collection)
        if stored_dimension is not None and stored_dimension != dimension and valid_records:
            raise DimensionMismatchError(collection_name, expected=stored_dimension, actual=dimension)

        indexed_count = await self._upsert_in_batches(collection, repository_name, valid_records)

        statistics = IndexStatistics(
            repository_name=repository_name,
            collection_name=collection_name,
            vectors_indexed=indexed_count,
            vectors_failed=invalid_count,
            dimension=dimension,
            distance_metric=self.settings.CHROMA_DISTANCE_METRIC,
            processing_time_seconds=round(time.perf_counter() - start_time, 3),
            indexed_at=datetime.now(timezone.utc),
        )

        logger.info(
            "Indexing complete | repo=%s | collection=%s | indexed=%d | failed=%d | time=%.3fs",
            repository_name,
            collection_name,
            indexed_count,
            invalid_count,
            statistics.processing_time_seconds,
        )
        self._LAST_INDEX_CACHE[repository_name] = statistics
        return statistics

    def get_last_index_run(self, repository_name: str) -> Optional[IndexStatistics]:
        """Returns the most recent `IndexStatistics` for `repository_name`, or None if
        it has never been indexed this process lifetime. Used by the Analytics module."""
        return self._LAST_INDEX_CACHE.get(repository_name)

    # ------------------------------------------------------------------
    # Search
    # ------------------------------------------------------------------
    async def search(
        self,
        repository_name: str,
        query_text: Optional[str] = None,
        query_embedding: Optional[List[float]] = None,
        top_k: int = 5,
        score_threshold: Optional[float] = None,
        language: Optional[str] = None,
        file_name: Optional[str] = None,
        metadata_filters: Optional[Dict[str, Any]] = None,
    ) -> List[SearchResult]:
        """
        Similarity search within one repository's collection.

        Raises:
            CollectionNotFoundError: repository never indexed.
            EmptyCollectionError: collection exists but has zero vectors.
            DimensionMismatchError: query vector doesn't match the collection's dimension.
        """
        collection_name = self._build_collection_name(repository_name)
        collection = await asyncio.to_thread(self.client.get_collection, collection_name)
        if collection is None:
            raise CollectionNotFoundError(collection_name)

        count = await asyncio.to_thread(self.repo.count, collection)
        if count == 0:
            raise EmptyCollectionError(collection_name)

        vector = query_embedding
        if query_text is not None:
            vector, _, _ = await self.embedding_service.embed_text(query_text)

        expected_dim = self.client.get_collection_dimension(collection)
        if expected_dim is not None and vector is not None and len(vector) != expected_dim:
            raise DimensionMismatchError(collection_name, expected=expected_dim, actual=len(vector))

        effective_top_k = min(top_k, self.settings.MAX_TOP_K)
        where = self._build_where_clause(language, file_name, metadata_filters)

        raw = await asyncio.to_thread(self.repo.query, collection, vector, effective_top_k, where)
        results = self._parse_search_results(raw)

        threshold = score_threshold if score_threshold is not None else self.settings.DEFAULT_SCORE_THRESHOLD
        if threshold:
            results = [r for r in results if r.score >= threshold]

        return results

    # ------------------------------------------------------------------
    # Update
    # ------------------------------------------------------------------
    async def update_documents(self, repository_name: str, updates: List[Any]) -> int:
        """
        Partial update of existing vectors by document ID. Each item may
        update its content, embedding, and/or metadata independently.

        ChromaDB's `update()` applies uniformly across an entire call
        (it can't mix "update embedding" and "leave embedding alone"
        within one call), so each item is applied as its own call — still
        exposed as a single batch API request to the client.
        """
        collection_name = self._build_collection_name(repository_name)
        collection = await asyncio.to_thread(self.client.get_collection, collection_name)
        if collection is None:
            raise CollectionNotFoundError(collection_name)

        updated = 0
        for item in updates:
            embeddings = [item.embedding] if item.embedding is not None else None
            documents = [item.content] if item.content is not None else None
            metadatas = [item.metadata] if item.metadata is not None else None

            await asyncio.to_thread(
                self.repo.update,
                collection,
                [item.document_id],
                embeddings,
                documents,
                metadatas,
            )
            updated += 1

        logger.info("Updated documents | repo=%s | count=%d", repository_name, updated)
        return updated

    # ------------------------------------------------------------------
    # Delete
    # ------------------------------------------------------------------
    async def delete_documents(
        self,
        repository_name: str,
        document_ids: Optional[List[str]] = None,
        file_name: Optional[str] = None,
        delete_all: bool = False,
    ) -> int:
        collection_name = self._build_collection_name(repository_name)
        collection = await asyncio.to_thread(self.client.get_collection, collection_name)
        if collection is None:
            raise CollectionNotFoundError(collection_name)

        if delete_all:
            existing = await asyncio.to_thread(self.repo.get, collection, None, 0, None)
            ids_to_delete = existing.get("ids", [])
            if ids_to_delete:
                await asyncio.to_thread(self.repo.delete, collection, ids_to_delete, None)
            deleted_count = len(ids_to_delete)
        elif file_name:
            where = {"file_name": file_name}
            existing = await asyncio.to_thread(self.repo.get, collection, None, 0, where)
            deleted_count = len(existing.get("ids", []))
            if deleted_count:
                await asyncio.to_thread(self.repo.delete, collection, None, where)
        else:
            deleted_count = len(document_ids or [])
            if deleted_count:
                await asyncio.to_thread(self.repo.delete, collection, document_ids, None)

        logger.info("Deleted documents | repo=%s | count=%d", repository_name, deleted_count)
        return deleted_count

    # ------------------------------------------------------------------
    # Collections
    # ------------------------------------------------------------------
    async def list_collections(self) -> List[CollectionInfo]:
        names = await asyncio.to_thread(self.client.list_collection_names)
        infos: List[CollectionInfo] = []

        for name in names:
            if not name.startswith(self.settings.COLLECTION_NAME_PREFIX):
                continue
            collection = await asyncio.to_thread(self.client.get_collection, name)
            if collection is None:
                continue
            count = await asyncio.to_thread(self.repo.count, collection)
            infos.append(
                CollectionInfo(
                    collection_name=name,
                    repository_name=name[len(self.settings.COLLECTION_NAME_PREFIX) :],
                    vector_count=count,
                    dimension=self.client.get_collection_dimension(collection),
                    distance_metric=self.settings.CHROMA_DISTANCE_METRIC,
                )
            )
        return infos

    async def delete_collection(self, collection_name: str) -> None:
        exists = await asyncio.to_thread(self.client.collection_exists, collection_name)
        if not exists:
            raise CollectionNotFoundError(collection_name)
        await asyncio.to_thread(self.client.delete_collection, collection_name)
        logger.info("Collection deleted | collection=%s", collection_name)

    # ------------------------------------------------------------------
    # Statistics
    # ------------------------------------------------------------------
    async def get_statistics(self, repository_name: str) -> VectorStatistics:
        collection_name = self._build_collection_name(repository_name)
        collection = await asyncio.to_thread(self.client.get_collection, collection_name)
        if collection is None:
            raise CollectionNotFoundError(collection_name)

        total = await asyncio.to_thread(self.repo.count, collection)
        language_counts: Dict[str, int] = {}
        unique_files = 0

        if total > 0:
            raw = await asyncio.to_thread(self.repo.get, collection, None, 0, None)
            metadatas = raw.get("metadatas", []) or []
            language_counts = dict(Counter(m.get("language", "Unknown") for m in metadatas))
            unique_files = len({m.get("relative_path") for m in metadatas if m.get("relative_path")})

        return VectorStatistics(
            repository_name=repository_name,
            collection_name=collection_name,
            total_vectors=total,
            dimension=self.client.get_collection_dimension(collection),
            distance_metric=self.settings.CHROMA_DISTANCE_METRIC,
            language_counts=language_counts,
            unique_files=unique_files,
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _build_collection_name(self, repository_name: str) -> str:
        sanitized = _INVALID_COLLECTION_CHARS.sub("_", repository_name)
        return f"{self.settings.COLLECTION_NAME_PREFIX}{sanitized}"[:63]

    @staticmethod
    def _make_repository_id(repository_name: str) -> str:
        return hashlib.sha256(repository_name.encode("utf-8")).hexdigest()[:12]

    def _validate_records(
        self, records: List[EmbeddingRecord]
    ) -> Tuple[List[EmbeddingRecord], int]:
        """Filters out records with empty/malformed vectors; logs and counts them as failed."""
        valid: List[EmbeddingRecord] = []
        invalid_count = 0
        expected_dim: Optional[int] = None

        for record in records:
            if not record.embedding:
                logger.warning("Skipping record with empty embedding | id=%s", record.document_id)
                invalid_count += 1
                continue
            if expected_dim is None:
                expected_dim = len(record.embedding)
            elif len(record.embedding) != expected_dim:
                logger.warning(
                    "Skipping record with inconsistent dimension | id=%s | expected=%d | actual=%d",
                    record.document_id,
                    expected_dim,
                    len(record.embedding),
                )
                invalid_count += 1
                continue
            valid.append(record)

        return valid, invalid_count

    async def _upsert_in_batches(
        self, collection: Any, repository_name: str, records: List[EmbeddingRecord]
    ) -> int:
        if not records:
            return 0

        repository_id = self._make_repository_id(repository_name)
        now = datetime.now(timezone.utc).isoformat()
        batch_size = self.settings.BATCH_UPSERT_SIZE
        indexed = 0

        for i in range(0, len(records), batch_size):
            batch = records[i : i + batch_size]
            ids = [r.document_id for r in batch]
            embeddings = [r.embedding for r in batch]
            documents: List[str] = []
            metadatas: List[Dict[str, Any]] = []

            for record in batch:
                meta = record.metadata
                documents.append("")  # content lives in Step 5/6 caches; store metadata-only here
                metadatas.append(
                    {
                        "repository_name": meta.repository_name,
                        "repository_id": repository_id,
                        "file_name": Path(meta.relative_file_path).name,
                        "relative_path": meta.relative_file_path,
                        "language": meta.language,
                        "extension": meta.extension,
                        "chunk_number": meta.chunk_number,
                        "total_chunks": meta.total_chunks,
                        "lines_of_code": meta.lines_of_code,
                        "timestamp": now,
                    }
                )

            await asyncio.to_thread(self.repo.upsert, collection, ids, embeddings, documents, metadatas)
            indexed += len(batch)
            logger.info(
                "Upsert batch complete | repo=%s | batch=%d-%d/%d",
                repository_name,
                i + 1,
                i + len(batch),
                len(records),
            )

        return indexed

    def _build_where_clause(
        self,
        language: Optional[str],
        file_name: Optional[str],
        metadata_filters: Optional[Dict[str, Any]],
    ) -> Optional[Dict[str, Any]]:
        conditions: List[Dict[str, Any]] = []
        if language:
            conditions.append({"language": language})
        if file_name:
            conditions.append({"file_name": file_name})
        if metadata_filters:
            conditions.append(metadata_filters)

        if not conditions:
            return None
        if len(conditions) == 1:
            return conditions[0]
        return {"$and": conditions}

    def _parse_search_results(self, raw: Dict[str, Any]) -> List[SearchResult]:
        ids = (raw.get("ids") or [[]])[0]
        documents = (raw.get("documents") or [[]])[0]
        metadatas = (raw.get("metadatas") or [[]])[0]
        distances = (raw.get("distances") or [[]])[0]

        results: List[SearchResult] = []
        for doc_id, content, metadata, distance in zip(ids, documents, metadatas, distances):
            score = self._distance_to_score(distance)
            try:
                vector_metadata = VectorMetadata(**metadata)
            except Exception as exc:  # noqa: BLE001
                logger.warning("Malformed stored metadata for %s: %s", doc_id, exc)
                continue

            results.append(
                SearchResult(
                    document_id=doc_id,
                    content=content or "",
                    metadata=vector_metadata,
                    score=score,
                    distance=distance,
                )
            )
        return results

    def _distance_to_score(self, distance: float) -> float:
        """
        Converts a raw ChromaDB distance to a 0-1 similarity score (higher
        = more similar). For cosine distance (1 - cosine_similarity), this
        is a direct subtraction; for other metrics a bounded inverse is
        used as a reasonable general-purpose normalization.
        """
        if self.settings.CHROMA_DISTANCE_METRIC == "cosine":
            return max(0.0, min(1.0, 1.0 - distance))
        return round(1.0 / (1.0 + max(0.0, distance)), 6)


def get_vector_store_service(
    chromadb_client: ChromaDBClient = Depends(get_chromadb_client),
    embedding_service: EmbeddingService = Depends(get_embedding_service),
) -> VectorStoreService:
    """FastAPI dependency provider — see app/api/vector_store.py."""
    return VectorStoreService(chromadb_client=chromadb_client, embedding_service=embedding_service)
