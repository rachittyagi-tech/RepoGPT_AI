"""
app/services/embedding_service.py

Business logic for the Embedding Generation Layer (Step 6).

Responsibilities:
    - Provider factory: instantiates the configured/requested embedding
      provider from a small registry (Strategy pattern) — adding a new
      provider later means adding one line to `_PROVIDER_REGISTRY`, never
      touching this class's control flow (Open/Closed Principle)
    - Batches chunks (from Step 5's ChunkingService) by BATCH_SIZE
    - Applies ONE generic retry-with-backoff + per-batch timeout policy
      across every provider (so Gemini/HuggingFace/future providers never
      duplicate this logic — DRY)
    - Builds a deterministic `document_id` per chunk, preserves its full
      Step 5 metadata unchanged
    - Aggregates processing-time and chunk-count statistics
    - Logs batch-level progress ("batch 3/12 complete")

Clean Architecture note: like `ChunkingService`, this class itself has no
FastAPI import — only the `get_embedding_service` provider function at
the bottom uses `Depends`.
"""

from __future__ import annotations

import asyncio
import hashlib
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import ClassVar, Dict, List, Optional, Tuple, Type

from fastapi import Depends

from app.core.embedding_config import EmbeddingSettings, get_embedding_settings
from app.core.exceptions import (
    EmbeddingAuthError,
    EmbeddingProviderError,
    EmbeddingProviderNotConfiguredError,
    EmbeddingRateLimitError,
    EmbeddingTimeoutError,
    EmbeddingsNotGeneratedError,
    InvalidEmbeddingProviderError,
    NoDocumentsToEmbedError,
)
from app.core.logging import get_logger
from app.providers.base_embedding import BaseEmbeddingProvider
from app.providers.gemini_embedding import GeminiEmbeddingProvider
from app.providers.huggingface_embedding import HuggingFaceEmbeddingProvider
from app.schemas.chunking import ChunkRecord
from app.schemas.embedding import EmbeddingRecord, EmbeddingStatistics, ProviderInfo
from app.services.chunking_service import ChunkingService, get_chunking_service

logger = get_logger("services.embedding")


def make_document_id(repository_name: str, relative_file_path: str, chunk_number: int) -> str:
    """
    Deterministic ID from repo + relative file path + chunk number, so
    re-running the pipeline on the same repo produces the same IDs
    (important for ChromaDB upsert semantics in Step 7, and for Step 8's
    RetrieverService to re-hydrate a search hit's chunk content from
    Step 5's cache using this same ID).

    Module-level (not a method) because it's a pure function shared
    across services — DRY, and avoids Step 8 needing to reach into
    EmbeddingService's internals.
    """
    raw = f"{repository_name}:{relative_file_path}:{chunk_number}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:24]

# ---------------------------------------------------------------------------
# Provider registry — the ONLY place that needs to change to add a new
# implemented provider. Planned-but-not-yet-implemented providers are
# listed separately (`_PLANNED_PROVIDERS`) purely for the /providers
# endpoint's informational listing.
# ---------------------------------------------------------------------------
_PROVIDER_REGISTRY: Dict[str, Type[BaseEmbeddingProvider]] = {
    "gemini": GeminiEmbeddingProvider,
    "huggingface": HuggingFaceEmbeddingProvider,
}

_PLANNED_PROVIDERS: List[str] = ["openai", "voyage", "jina", "azure_openai"]


@dataclass
class _BatchOutcome:
    vectors: List[List[float]]
    elapsed_seconds: float
    succeeded: bool


class EmbeddingService:
    """Converts a repository's chunked Documents into embedding vectors."""

    # Provider instances are expensive to build (HF loads a model into
    # memory, Gemini configures an SDK client) — cache one instance per
    # provider name for the lifetime of the process, shared across requests.
    _PROVIDER_INSTANCES: ClassVar[Dict[str, BaseEmbeddingProvider]] = {}

    # Most recent run's statistics per repository — backs GET /api/embeddings/status.
    _LAST_RUN_BY_REPO: ClassVar[Dict[str, EmbeddingStatistics]] = {}

    # Most recent run's full records (WITH vectors) per repository — consumed
    # by Step 7's VectorStoreService to index into ChromaDB. Kept separate
    # from the API response layer's optional `include_vectors=false`
    # stripping (app/api/embeddings.py), which only affects what's returned
    # over HTTP, never what's cached here.
    _LAST_RECORDS_BY_REPO: ClassVar[Dict[str, List[EmbeddingRecord]]] = {}

    def __init__(
        self,
        chunking_service: ChunkingService,
        settings: Optional[EmbeddingSettings] = None,
    ) -> None:
        self.chunking_service = chunking_service
        self.settings = settings or get_embedding_settings()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    async def generate_embeddings(
        self,
        repository_name: str,
        provider_override: Optional[str] = None,
        batch_size_override: Optional[int] = None,
    ) -> Tuple[EmbeddingStatistics, List[EmbeddingRecord]]:
        """
        Generates embeddings for every cached chunk of `repository_name`.

        Raises:
            ChunkingNotPerformedError: propagated from ChunkingService if
                the repository was never chunked.
            NoDocumentsToEmbedError: if chunking produced zero chunks.
            InvalidEmbeddingProviderError: unknown provider name requested.
            EmbeddingProviderNotConfiguredError: provider missing required config.
            EmbeddingAuthError: provider rejected credentials.
        """
        chunks = self.chunking_service.get_cached_chunks(repository_name)
        if not chunks:
            raise NoDocumentsToEmbedError(repository_name)

        provider_name = (provider_override or self.settings.EMBEDDING_PROVIDER).lower()
        provider = self._get_provider(provider_name)

        if not provider.is_configured():
            raise EmbeddingProviderNotConfiguredError(
                provider_name,
                reason="Missing API key or model failed to load — check server logs.",
            )

        batch_size = batch_size_override or self.settings.BATCH_SIZE
        batches = [chunks[i : i + batch_size] for i in range(0, len(chunks), batch_size)]

        logger.info(
            "Starting embedding generation | repo=%s | provider=%s | model=%s | chunks=%d | batches=%d",
            repository_name,
            provider.provider_name,
            provider.model_name,
            len(chunks),
            len(batches),
        )

        records: List[EmbeddingRecord] = []
        failed_count = 0
        total_time = 0.0

        for batch_index, batch in enumerate(batches, start=1):
            outcome = await self._process_batch(provider, batch)
            total_time += outcome.elapsed_seconds

            if outcome.succeeded:
                per_doc_time = outcome.elapsed_seconds / len(batch) if batch else 0.0
                for chunk, vector in zip(batch, outcome.vectors):
                    records.append(self._build_record(chunk, vector, per_doc_time, provider))
            else:
                failed_count += len(batch)

            logger.info(
                "Batch progress | repo=%s | batch=%d/%d | status=%s",
                repository_name,
                batch_index,
                len(batches),
                "ok" if outcome.succeeded else "failed",
            )

        statistics = EmbeddingStatistics(
            repository_name=repository_name,
            provider=provider.provider_name,
            model=provider.model_name,
            dimension=provider.dimension,
            total_documents=len(chunks),
            embeddings_created=len(records),
            embeddings_failed=failed_count,
            batches_processed=len(batches),
            batch_size=batch_size,
            total_processing_time_seconds=round(total_time, 3),
            average_time_per_document_seconds=(
                round(total_time / len(records), 4) if records else 0.0
            ),
            generated_at=datetime.now(timezone.utc),
        )

        self._LAST_RUN_BY_REPO[repository_name] = statistics
        self._LAST_RECORDS_BY_REPO[repository_name] = records

        logger.info(
            "Embedding generation complete | repo=%s | created=%d | failed=%d | time=%.3fs",
            repository_name,
            statistics.embeddings_created,
            statistics.embeddings_failed,
            statistics.total_processing_time_seconds,
        )
        return statistics, records

    def get_cached_records(self, repository_name: str) -> List[EmbeddingRecord]:
        """
        Returns the full embedding records (including vectors) from the
        last /generate run for `repository_name`. Used by Step 7's
        VectorStoreService to index into ChromaDB.

        Raises:
            EmbeddingsNotGeneratedError: if /generate hasn't been run yet.
        """
        records = self._LAST_RECORDS_BY_REPO.get(repository_name)
        if not records:
            raise EmbeddingsNotGeneratedError(repository_name)
        return records

    async def embed_text(
        self, text: str, provider_override: Optional[str] = None
    ) -> Tuple[List[float], str, str]:
        """
        Embeds a single arbitrary text string (e.g. a search query) using
        the same provider/retry/timeout policy as batch generation.

        Returns `(vector, provider_name, model_name)` so callers (e.g. the
        vector search endpoint) can verify the query vector's dimension
        matches the collection it's about to search.
        """
        provider_name = (provider_override or self.settings.EMBEDDING_PROVIDER).lower()
        provider = self._get_provider(provider_name)

        if not provider.is_configured():
            raise EmbeddingProviderNotConfiguredError(
                provider_name,
                reason="Missing API key or model failed to load — check server logs.",
            )

        vectors = await self._embed_with_retry(provider, [text])
        return vectors[0], provider.provider_name, provider.model_name

    def list_providers(self) -> List[ProviderInfo]:
        """Returns availability info for every implemented + planned provider."""
        infos: List[ProviderInfo] = []

        for name in _PROVIDER_REGISTRY:
            provider = self._get_provider(name)
            infos.append(
                ProviderInfo(
                    name=name,
                    display_name=name.capitalize(),
                    status="available" if provider.is_configured() else "not_configured",
                    model=provider.model_name,
                    dimension=provider.dimension,
                    requires_api_key=name == "gemini",
                )
            )

        for name in _PLANNED_PROVIDERS:
            infos.append(
                ProviderInfo(
                    name=name,
                    display_name=name.replace("_", " ").title(),
                    status="planned",
                    requires_api_key=True,
                    notes="Architecture supports this provider; implementation lands in a future step.",
                )
            )

        return infos

    def get_status(self) -> Tuple[BaseEmbeddingProvider, Optional[EmbeddingStatistics]]:
        """Returns the currently-configured default provider and the most recent run, if any."""
        provider = self._get_provider(self.settings.EMBEDDING_PROVIDER)
        last_run = max(
            self._LAST_RUN_BY_REPO.values(), key=lambda s: s.generated_at, default=None
        )
        return provider, last_run

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _get_provider(self, provider_name: str) -> BaseEmbeddingProvider:
        if provider_name not in _PROVIDER_REGISTRY:
            raise InvalidEmbeddingProviderError(provider_name, available=list(_PROVIDER_REGISTRY.keys()))

        if provider_name not in self._PROVIDER_INSTANCES:
            provider_class = _PROVIDER_REGISTRY[provider_name]
            self._PROVIDER_INSTANCES[provider_name] = provider_class(self.settings)

        return self._PROVIDER_INSTANCES[provider_name]

    async def _process_batch(
        self, provider: BaseEmbeddingProvider, batch: List[ChunkRecord]
    ) -> _BatchOutcome:
        texts = [chunk.content for chunk in batch]
        start = time.perf_counter()

        try:
            vectors = await self._embed_with_retry(provider, texts)
            elapsed = time.perf_counter() - start
            return _BatchOutcome(vectors=vectors, elapsed_seconds=elapsed, succeeded=True)
        except EmbeddingAuthError:
            # Invalid credentials won't fix themselves on the next batch —
            # fail the whole request immediately instead of retrying N more
            # times with the same bad key.
            raise
        except Exception as exc:  # noqa: BLE001
            elapsed = time.perf_counter() - start
            logger.error("Batch failed permanently after retries | error=%s", exc)
            return _BatchOutcome(vectors=[], elapsed_seconds=elapsed, succeeded=False)

    async def _embed_with_retry(
        self, provider: BaseEmbeddingProvider, texts: List[str]
    ) -> List[List[float]]:
        """
        Generic retry-with-exponential-backoff + per-attempt timeout,
        shared by every provider. Auth errors are never retried (see
        `_process_batch`); rate-limit/timeout/generic provider errors are
        retried up to `MAX_RETRIES` additional times.
        """
        max_attempts = self.settings.MAX_RETRIES + 1
        last_exc: Exception = EmbeddingProviderError(provider.provider_name, "Unknown failure.")

        for attempt in range(1, max_attempts + 1):
            try:
                return await asyncio.wait_for(
                    provider.embed_batch(texts), timeout=self.settings.TIMEOUT
                )
            except EmbeddingAuthError:
                raise
            except asyncio.TimeoutError:
                last_exc = EmbeddingTimeoutError(provider.provider_name, self.settings.TIMEOUT)
            except (EmbeddingRateLimitError, EmbeddingProviderError) as exc:
                last_exc = exc

            if attempt < max_attempts:
                backoff_seconds = 2 ** (attempt - 1)
                logger.warning(
                    "Embedding attempt %d/%d failed (%s) — retrying in %ds...",
                    attempt,
                    max_attempts,
                    last_exc,
                    backoff_seconds,
                )
                await asyncio.sleep(backoff_seconds)

        raise last_exc

    @staticmethod
    def _build_record(
        chunk: ChunkRecord,
        vector: List[float],
        processing_time: float,
        provider: BaseEmbeddingProvider,
    ) -> EmbeddingRecord:
        document_id = make_document_id(
            chunk.metadata.repository_name,
            chunk.metadata.relative_file_path,
            chunk.metadata.chunk_number,
        )
        return EmbeddingRecord(
            document_id=document_id,
            embedding=vector,
            metadata=chunk.metadata,
            processing_time_seconds=round(processing_time, 4),
            dimension=provider.dimension,
        )


def get_embedding_service(
    chunking_service: ChunkingService = Depends(get_chunking_service),
) -> EmbeddingService:
    """FastAPI dependency provider — see app/api/embeddings.py."""
    return EmbeddingService(chunking_service=chunking_service)
