"""
app/providers/gemini_embedding.py

Google Gemini embedding provider implementation.

Uses Google's Generative AI SDK to generate embeddings.
The synchronous SDK call is executed in a worker thread so it
does not block FastAPI's async event loop.
"""

from __future__ import annotations

import asyncio
from typing import List

from app.core.embedding_config import EmbeddingSettings
from app.core.exceptions import (
    EmbeddingAuthError,
    EmbeddingProviderError,
    EmbeddingRateLimitError,
)
from app.core.logging import get_logger
from app.providers.base_embedding import BaseEmbeddingProvider

logger = get_logger("providers.gemini")


# Known output dimensionality for supported Gemini embedding models.
_MODEL_DIMENSIONS = {
    "gemini-embedding-001": 3072,
    "gemini-embedding-2-preview": 3072,
    "gemini-embedding-2": 3072,
}

_DEFAULT_DIMENSION = 3072


_AUTH_ERROR_MARKERS = (
    "api key",
    "unauthorized",
    "permission denied",
    "invalid api key",
    "authentication",
)

_RATE_LIMIT_MARKERS = (
    "quota",
    "rate limit",
    "resource exhausted",
    "429",
)


class GeminiEmbeddingProvider(BaseEmbeddingProvider):
    """Embedding provider backed by Google's Gemini embedding models."""

    def __init__(self, settings: EmbeddingSettings) -> None:
        self._settings = settings
        self._model = settings.GEMINI_EMBEDDING_MODEL
        self._configured = bool(settings.GEMINI_API_KEY)
        self._client_ready = False

        if self._configured:
            self._configure_client()

    def _configure_client(self) -> None:
        """Configure the Google Generative AI SDK."""
        import google.generativeai as genai

        genai.configure(api_key=self._settings.GEMINI_API_KEY)
        self._client_ready = True

    @property
    def provider_name(self) -> str:
        return "gemini"

    @property
    def model_name(self) -> str:
        return self._model

    @property
    def dimension(self) -> int:
        return _MODEL_DIMENSIONS.get(
            self._model,
            _DEFAULT_DIMENSION,
        )

    def is_configured(self) -> bool:
        return self._configured and self._client_ready

    async def embed_batch(
        self,
        texts: List[str],
    ) -> List[List[float]]:
        """
        Generate embeddings for a batch of texts.

        The Gemini SDK call is synchronous, so it runs inside
        asyncio.to_thread() to keep the FastAPI event loop responsive.
        """

        if not self.is_configured():
            raise EmbeddingAuthError(self.provider_name)

        if not texts:
            return []

        try:
            embeddings = await asyncio.to_thread(
                self._embed_batch_sync,
                texts,
            )

            # Validate dimensionality.
            for embedding in embeddings:
                if len(embedding) != self.dimension:
                    raise EmbeddingProviderError(
                        self.provider_name,
                        (
                            f"Unexpected embedding dimension: "
                            f"{len(embedding)}. "
                            f"Expected: {self.dimension}."
                        ),
                    )

            return embeddings

        except (
            EmbeddingAuthError,
            EmbeddingRateLimitError,
            EmbeddingProviderError,
        ):
            raise

        except Exception as exc:
            raise self._classify_error(exc) from exc

    def _embed_batch_sync(
        self,
        texts: List[str],
    ) -> List[List[float]]:
        """Synchronous Gemini embedding request."""

        import google.generativeai as genai

        try:
            result = genai.embed_content(
                model=f"models/{self._model}",
                content=texts,
                task_type="retrieval_document",
            )

        except Exception as exc:
            raise self._classify_error(exc) from exc

        embeddings = result.get("embedding")

        if embeddings is None:
            raise EmbeddingProviderError(
                self.provider_name,
                "Response missing 'embedding' field.",
            )

        if not embeddings:
            raise EmbeddingProviderError(
                self.provider_name,
                "Gemini returned an empty embedding response.",
            )

        # Single text:
        #   [0.1, 0.2, ...]
        #
        # Multiple texts:
        #   [[0.1, 0.2, ...], [0.3, 0.4, ...]]
        if isinstance(embeddings[0], (float, int)):
            return [list(embeddings)]

        return [list(vector) for vector in embeddings]

    def _classify_error(self, exc: Exception) -> Exception:
        """Convert Gemini SDK exceptions into application exceptions."""

        message = str(exc).lower()

        if any(
            marker in message
            for marker in _AUTH_ERROR_MARKERS
        ):
            logger.warning(
                "Gemini authentication failure: %s",
                exc,
            )
            return EmbeddingAuthError(self.provider_name)

        if any(
            marker in message
            for marker in _RATE_LIMIT_MARKERS
        ):
            logger.warning(
                "Gemini rate limited: %s",
                exc,
            )
            return EmbeddingRateLimitError(self.provider_name)

        logger.error(
            "Gemini provider error: %s",
            exc,
        )

        return EmbeddingProviderError(
            self.provider_name,
            reason=str(exc),
        )