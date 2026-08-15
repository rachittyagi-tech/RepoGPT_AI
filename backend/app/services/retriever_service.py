"""
app/services/retriever_service.py

Wraps Step 7's `VectorStoreService` to perform the "Vector Search
(ChromaDB)" + "Metadata Filtering" stages of the RAG pipeline, and
re-hydrates each hit's actual chunk text.

Why re-hydration is needed: Step 7 deliberately stores ChromaDB vectors
with empty `documents` (metadata + vectors only, to keep the vector store
lean) — see `vector_store_service.py`. The actual chunk text lives in
Step 5's `ChunkingService` in-memory cache. This service reunites a
ChromaDB hit with its text using the same deterministic `document_id`
formula Step 6 established (repo + relative_path + chunk_number).

Known limitation (documented, not fixed here — out of Step 8's scope):
Steps 4-6's caches are in-process and NOT persisted, while ChromaDB IS
persisted. After a server restart, previously-indexed vectors still exist
in ChromaDB, but retrieval will fail with `ChunkingNotPerformedError`
until the repository is re-scanned/re-chunked. A future step could store
chunk content directly in ChromaDB's `documents` field (trading some
storage size for resilience) to remove this dependency.
"""

from __future__ import annotations

from typing import Dict, List, Optional

from fastapi import Depends

from app.core.logging import get_logger
from app.schemas.rag import RetrievedChunk
from app.services.chunking_service import ChunkingService, get_chunking_service
from app.services.embedding_service import make_document_id
from app.services.vector_store_service import VectorStoreService, get_vector_store_service

logger = get_logger("services.retriever")


class RetrieverService:
    """Performs vector similarity search and re-hydrates chunk content for the RAG pipeline."""

    def __init__(
        self,
        vector_store_service: VectorStoreService,
        chunking_service: ChunkingService,
    ) -> None:
        self.vector_store_service = vector_store_service
        self.chunking_service = chunking_service

    async def retrieve(
        self,
        repository_name: str,
        query_text: str,
        top_k: int,
        score_threshold: Optional[float],
        language: Optional[str] = None,
        file_name: Optional[str] = None,
    ) -> List[RetrievedChunk]:
        """
        Runs similarity search (Step 7) and re-attaches each hit's actual
        chunk content from Step 5's cache.

        Propagates Step 7's exceptions unchanged: `CollectionNotFoundError`
        (repository never indexed), `EmptyCollectionError` (indexed but
        zero vectors), `DimensionMismatchError`. Propagates
        `ChunkingNotPerformedError` from Step 5 if the chunk cache is gone.
        """
        search_results = await self.vector_store_service.search(
            repository_name=repository_name,
            query_text=query_text,
            top_k=top_k,
            score_threshold=score_threshold,
            language=language,
            file_name=file_name,
        )

        content_by_id = self._build_content_lookup(repository_name)

        chunks: List[RetrievedChunk] = []
        missing = 0
        for result in search_results:
            content = content_by_id.get(result.document_id)
            if content is None:
                missing += 1
                logger.warning(
                    "No cached content for retrieved chunk %s (repo=%s) — "
                    "was the repository re-chunked after indexing? Skipping.",
                    result.document_id,
                    repository_name,
                )
                continue

            chunks.append(
                RetrievedChunk(
                    document_id=result.document_id,
                    content=content,
                    score=result.score,
                    similarity_score=result.score,
                    repository_name=result.metadata.repository_name,
                    file_path=result.metadata.relative_path,
                    language=result.metadata.language,
                    extension=result.metadata.extension,
                    chunk_number=result.metadata.chunk_number,
                    total_chunks=result.metadata.total_chunks,
                    lines_of_code=result.metadata.lines_of_code,
                )
            )

        if missing:
            logger.warning(
                "Content hydration misses | repo=%s | missing=%d/%d",
                repository_name,
                missing,
                len(search_results),
            )

        return chunks

    def _build_content_lookup(self, repository_name: str) -> Dict[str, str]:
        """
        Builds a document_id -> content map from Step 5's cached chunks,
        using the same deterministic ID formula Step 6 used when embedding
        (and Step 7 used as the ChromaDB vector ID) — this is what lets us
        reunite a ChromaDB search hit with its actual text.
        """
        chunks = self.chunking_service.get_cached_chunks(repository_name)
        return {
            make_document_id(
                chunk.metadata.repository_name,
                chunk.metadata.relative_file_path,
                chunk.metadata.chunk_number,
            ): chunk.content
            for chunk in chunks
        }


def get_retriever_service(
    vector_store_service: VectorStoreService = Depends(get_vector_store_service),
    chunking_service: ChunkingService = Depends(get_chunking_service),
) -> RetrieverService:
    """FastAPI dependency provider — see app/services/rag_service.py."""
    return RetrieverService(
        vector_store_service=vector_store_service, chunking_service=chunking_service
    )
