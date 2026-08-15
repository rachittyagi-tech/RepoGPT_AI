"""
app/api/vector_store.py

HTTP layer for the ChromaDB Vector Store Layer module (Step 7).

Thin router — validates input via Pydantic, delegates to
`VectorStoreService`, shapes the response. Error translation (collection
not found, duplicate collection, dimension mismatch, empty collection,
search/persistence failures) happens via domain exceptions + the global
exception handlers from Step 2.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, status

from app.core.logging import get_logger
from app.schemas.vector_store import (
    CollectionsResponse,
    DeleteCollectionResponse,
    DeleteRequest,
    DeleteResponse,
    IndexRequest,
    IndexResponse,
    SearchRequest,
    SearchResponse,
    StatisticsResponse,
    UpdateRequest,
    UpdateResponse,
)
from app.services.vector_store_service import VectorStoreService, get_vector_store_service
from app.middleware.rate_limit import rate_limit

logger = get_logger("api.vector_store")

router = APIRouter(tags=["Vector Store"], dependencies=[Depends(rate_limit("vector_store", 10, 60))])


@router.post(
    "/index",
    response_model=IndexResponse,
    status_code=status.HTTP_200_OK,
    summary="Index a repository's embeddings into its ChromaDB collection",
)
async def index_repository(
    payload: IndexRequest,
    service: VectorStoreService = Depends(get_vector_store_service),
) -> IndexResponse:
    """
    Stores every cached embedding (from POST /api/embeddings/generate) for
    `repository_name` into a dedicated, isolated ChromaDB collection.
    Safe to call repeatedly — re-indexing upserts by deterministic ID
    rather than duplicating vectors.

    Returns 404 if embeddings were never generated, 400 if the resulting
    dimension conflicts with an existing collection's dimension.
    """
    logger.info("Received index request | repo=%s", payload.repository_name)
    statistics = await service.index_repository(
        payload.repository_name, force_recreate=payload.force_recreate
    )
    return IndexResponse(
        message=f"Indexed {statistics.vectors_indexed} vectors for '{payload.repository_name}'.",
        statistics=statistics,
    )


@router.post(
    "/search",
    response_model=SearchResponse,
    status_code=status.HTTP_200_OK,
    summary="Similarity search within a repository's vector collection",
)
async def search_vectors(
    payload: SearchRequest,
    service: VectorStoreService = Depends(get_vector_store_service),
) -> SearchResponse:
    """
    Runs a top-K similarity search against `repository_name`'s collection.
    Provide either `query_text` (embedded automatically using the
    configured provider) or a pre-computed `query_embedding`.

    Returns 404 if the repository was never indexed, 400 if the collection
    is empty, 400 on a query/collection dimension mismatch.
    """
    results = await service.search(
        repository_name=payload.repository_name,
        query_text=payload.query_text,
        query_embedding=payload.query_embedding,
        top_k=payload.top_k,
        score_threshold=payload.score_threshold,
        language=payload.language,
        file_name=payload.file_name,
        metadata_filters=payload.metadata_filters,
    )
    return SearchResponse(
        repository_name=payload.repository_name,
        query_text=payload.query_text,
        count=len(results),
        results=results,
    )


@router.put(
    "/update",
    response_model=UpdateResponse,
    status_code=status.HTTP_200_OK,
    summary="Batch-update existing vectors by document ID",
)
async def update_vectors(
    payload: UpdateRequest,
    service: VectorStoreService = Depends(get_vector_store_service),
) -> UpdateResponse:
    """
    Updates content, embedding, and/or metadata for one or more existing
    documents by ID. Each item updates only the fields it provides.

    Returns 404 if the repository's collection doesn't exist.
    """
    updated_count = await service.update_documents(payload.repository_name, payload.updates)
    return UpdateResponse(
        message=f"Updated {updated_count} vector(s) in '{payload.repository_name}'.",
        updated_count=updated_count,
    )


@router.delete(
    "/delete",
    response_model=DeleteResponse,
    status_code=status.HTTP_200_OK,
    summary="Batch-delete vectors by ID, file, or the entire repository",
)
async def delete_vectors(
    payload: DeleteRequest,
    service: VectorStoreService = Depends(get_vector_store_service),
) -> DeleteResponse:
    """
    Deletes vectors from `repository_name`'s collection — by explicit
    `document_ids`, by `file_name` (every chunk of one file), or entirely
    via `delete_all=true`.

    Returns 404 if the repository's collection doesn't exist.
    """
    deleted_count = await service.delete_documents(
        payload.repository_name,
        document_ids=payload.document_ids,
        file_name=payload.file_name,
        delete_all=payload.delete_all,
    )
    return DeleteResponse(
        message=f"Deleted {deleted_count} vector(s) from '{payload.repository_name}'.",
        deleted_count=deleted_count,
    )


@router.get(
    "/statistics",
    response_model=StatisticsResponse,
    status_code=status.HTTP_200_OK,
    summary="Get aggregate statistics for a repository's vector collection",
)
async def get_statistics(
    repository_name: str,
    service: VectorStoreService = Depends(get_vector_store_service),
) -> StatisticsResponse:
    """
    Returns total vector count, dimension, distance metric, per-language
    breakdown, and unique file count for `repository_name`.

    Returns 404 if the repository's collection doesn't exist.
    """
    statistics = await service.get_statistics(repository_name)
    return StatisticsResponse(statistics=statistics)


@router.get(
    "/collections",
    response_model=CollectionsResponse,
    status_code=status.HTTP_200_OK,
    summary="List every repository's vector collection",
)
async def list_collections(
    service: VectorStoreService = Depends(get_vector_store_service),
) -> CollectionsResponse:
    """Returns every RepoGPT-managed collection with its vector count and dimension."""
    collections = await service.list_collections()
    return CollectionsResponse(count=len(collections), collections=collections)


@router.delete(
    "/collection/{collection_name}",
    response_model=DeleteCollectionResponse,
    status_code=status.HTTP_200_OK,
    summary="Delete an entire collection (all vectors for one repository)",
)
async def delete_collection(
    collection_name: str,
    service: VectorStoreService = Depends(get_vector_store_service),
) -> DeleteCollectionResponse:
    """
    Permanently deletes `collection_name` (the full collection name, e.g.
    'repogpt_psf__requests', as returned by GET /api/vector/collections)
    and every vector it contains.

    Returns 404 if no such collection exists.
    """
    await service.delete_collection(collection_name)
    return DeleteCollectionResponse(
        message=f"Collection '{collection_name}' deleted successfully.",
        collection_name=collection_name,
    )
