"""
app/api/embeddings.py

HTTP layer for the Embedding Generation Layer module (Step 6).

Thin router — validates input via Pydantic, delegates to
`EmbeddingService`, shapes the response. Error translation (invalid
provider, not configured, auth/rate-limit/timeout/provider failures)
happens via domain exceptions + the global exception handlers.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, status

from app.core.logging import get_logger
from app.schemas.embedding import (
    EmbeddingGenerateRequest,
    EmbeddingGenerateResponse,
    EmbeddingStatusResponse,
    ProvidersResponse,
)
from app.services.embedding_service import EmbeddingService, get_embedding_service
from app.middleware.rate_limit import rate_limit

logger = get_logger("api.embeddings")

router = APIRouter(tags=["Embeddings"], dependencies=[Depends(rate_limit("embeddings", 10, 60))])


@router.post(
    "/generate",
    response_model=EmbeddingGenerateResponse,
    status_code=status.HTTP_200_OK,
    summary="Generate embeddings for a chunked repository",
)
async def generate_embeddings(
    payload: EmbeddingGenerateRequest,
    service: EmbeddingService = Depends(get_embedding_service),
) -> EmbeddingGenerateResponse:
    """
    Generates one embedding vector per chunk for `repository_name` (which
    must already be processed via POST /api/chunking/process), using the
    configured provider (`EMBEDDING_PROVIDER` in .env, or the `provider`
    override in this request).

    Returns 400 if there are no chunks to embed or the provider isn't
    configured, 401 if the provider rejects credentials, 404 if the
    provider name is unrecognized or chunking was never performed, 429
    on rate limiting, 504 on timeout, 502 for other provider failures.
    """
    logger.info(
        "Received embedding request | repo=%s | provider=%s",
        payload.repository_name,
        payload.provider or "(default)",
    )
    statistics, records = await service.generate_embeddings(
        payload.repository_name,
        provider_override=payload.provider,
        batch_size_override=payload.batch_size,
    )

    if not payload.include_vectors:
        records = [r.model_copy(update={"embedding": []}) for r in records]

    return EmbeddingGenerateResponse(
        message=(
            f"Generated {statistics.embeddings_created} embeddings for "
            f"'{payload.repository_name}' using {statistics.provider}."
        ),
        statistics=statistics,
        records=records,
    )


@router.get(
    "/providers",
    response_model=ProvidersResponse,
    status_code=status.HTTP_200_OK,
    summary="List available embedding providers and their configuration status",
)
async def list_providers(
    service: EmbeddingService = Depends(get_embedding_service),
) -> ProvidersResponse:
    """
    Returns every implemented provider (gemini, huggingface) with its
    live configuration status, plus architecturally-supported-but-not-yet-
    implemented providers (openai, voyage, jina, azure_openai) marked "planned".
    """
    providers = service.list_providers()
    return ProvidersResponse(
        active_provider=service.settings.EMBEDDING_PROVIDER,
        providers=providers,
    )


@router.get(
    "/status",
    response_model=EmbeddingStatusResponse,
    status_code=status.HTTP_200_OK,
    summary="Get the active provider's configuration and last run statistics",
)
async def get_status(
    service: EmbeddingService = Depends(get_embedding_service),
) -> EmbeddingStatusResponse:
    """Returns the currently active provider's readiness and, if any run has happened, its last statistics."""
    provider, last_run = service.get_status()
    return EmbeddingStatusResponse(
        active_provider=provider.provider_name,
        is_configured=provider.is_configured(),
        model=provider.model_name,
        dimension=provider.dimension if provider.is_configured() else None,
        batch_size=service.settings.BATCH_SIZE,
        max_retries=service.settings.MAX_RETRIES,
        timeout_seconds=service.settings.TIMEOUT,
        last_run=last_run,
    )
