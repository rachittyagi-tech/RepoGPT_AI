"""
app/providers/gemini_embedding.py

Google Gemini embedding provider implementation.

Uses the `google-generativeai` SDK's `embed_content` function, which
accepts a list of strings and returns one embedding per string. The SDK
call is synchronous, so it's wrapped in `asyncio.to_thread` to avoid
blocking the event loop.
"""

from __future__ import annotations

from typing import List

from app.core.embedding_config import EmbeddingSettings
from app.core.exceptions import EmbeddingAuthError, EmbeddingProviderError, EmbeddingRateLimitError
from app.core.logging import get_logger
from app.providers.base_embedding import BaseEmbeddingProvider

logger = get_logger("providers.gemini")

# Known output dimensionality per Gemini embedding model. Used to answer
# `.dimension` without making a network call.
_MODEL_DIMENSIONS = {
    "text-embedding-004": 768,
    "embedding-001": 768,
}
_DEFAULT_DIMENSION = 768

# Substrings used to classify google-generativeai's raised exceptions into
# our standard error types (mirrors the approach in github_service's
# `_classify_git_error` — keeps error handling consistent app-wide).
_AUTH_ERROR_MARKERS = ("api key", "unauthorized", "permission denied", "invalid api key")
_RATE_LIMIT_MARKERS = ("quota", "rate limit", "resource exhausted", "429")


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
        """Lazily imports and configures the SDK — avoids a hard import-time
        dependency on google-generativeai if Gemini is never used."""
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
        return _MODEL_DIMENSIONS.get(self._model, _DEFAULT_DIMENSION)

    def is_configured(self) -> bool:
        return self._configured and self._client_ready

    async def embed_batch(self, texts: List[str]) -> List[List[float]]:
        import asyncio

        if not self.is_configured():
            raise EmbeddingAuthError(self.provider_name)

        try:
            return await asyncio.to_thread(self._embed_batch_sync, texts)
        except (EmbeddingAuthError, EmbeddingRateLimitError, EmbeddingProviderError):
            raise
        except Exception as exc:  # noqa: BLE001
            raise self._classify_error(exc) from exc

    def _embed_batch_sync(self, texts: List[str]) -> List[List[float]]:
        import google.generativeai as genai

        try:
            result = genai.embed_content(
                model=f"models/{self._model}",
                content=texts,
                task_type="retrieval_document",
            )
        except Exception as exc:  # noqa: BLE001
            raise self._classify_error(exc) from exc

        embeddings = result.get("embedding")
        if embeddings is None:
            raise EmbeddingProviderError(self.provider_name, "Response missing 'embedding' field.")

        # The SDK returns a single vector (List[float]) when given one string
        # and a list of vectors when given a list — normalize to always be
        # a list of vectors so callers don't need to special-case batch size 1.
        if texts and isinstance(embeddings[0], float):
            return [embeddings]
        return embeddings

    def _classify_error(self, exc: Exception) -> Exception:
        message = str(exc).lower()

        if any(marker in message for marker in _AUTH_ERROR_MARKERS):
            logger.warning("Gemini auth failure: %s", exc)
            return EmbeddingAuthError(self.provider_name)

        if any(marker in message for marker in _RATE_LIMIT_MARKERS):
            logger.warning("Gemini rate limited: %s", exc)
            return EmbeddingRateLimitError(self.provider_name)

        logger.error("Gemini provider error: %s", exc)
        return EmbeddingProviderError(self.provider_name, reason=str(exc))
