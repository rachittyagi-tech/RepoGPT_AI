from __future__ import annotations

from typing import List, Optional

from fastapi import Depends

from app.core.logging import get_logger
from app.schemas.rag import RetrievedChunk
from app.services.vector_store_service import (
    VectorStoreService,
    get_vector_store_service,
)

logger = get_logger("services.retriever")


class RetrieverService:
    """Performs vector similarity search using persistent ChromaDB content."""

    def __init__(
        self,
        vector_store_service: VectorStoreService,
    ) -> None:
        self.vector_store_service = vector_store_service

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
        Runs vector similarity search and uses the chunk content returned
        directly from persistent ChromaDB.
        """

        search_results = await self.vector_store_service.search(
            repository_name=repository_name,
            query_text=query_text,
            top_k=top_k,
            score_threshold=score_threshold,
            language=language,
            file_name=file_name,
        )

        chunks: List[RetrievedChunk] = []

        for result in search_results:
            content = result.content or ""

            if not content:
                logger.warning(
                    "Empty content for retrieved chunk %s (repo=%s)",
                    result.document_id,
                    repository_name,
                )

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

        logger.info(
            "Retrieved chunks | repo=%s | count=%d",
            repository_name,
            len(chunks),
        )

        return chunks


def get_retriever_service(
    vector_store_service: VectorStoreService = Depends(get_vector_store_service),
) -> RetrieverService:
    """FastAPI dependency provider — see app/services/rag_service.py."""

    return RetrieverService(
        vector_store_service=vector_store_service,
    )
