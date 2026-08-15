"""
app/providers/huggingface_embedding.py

HuggingFace embedding provider implementation, backed by the
`sentence-transformers` library — runs entirely locally (no API key or
network call required), which is why it's the default provider for a
zero-config dev experience.

The model is loaded once (lazily, on first use) and cached at the class
level so repeated requests/DI instantiations don't reload it from disk
every time — loading a transformer model is expensive (hundreds of ms
to a few seconds) and should happen at most once per process.
"""

from __future__ import annotations

from typing import ClassVar, Dict, List, Optional

from app.core.embedding_config import EmbeddingSettings
from app.core.exceptions import EmbeddingProviderError
from app.core.logging import get_logger
from app.providers.base_embedding import BaseEmbeddingProvider

logger = get_logger("providers.huggingface")


class HuggingFaceEmbeddingProvider(BaseEmbeddingProvider):
    """Embedding provider backed by a local sentence-transformers model."""

    # Shared across instances so the (potentially large) model is loaded
    # into memory at most once per process, keyed by model name in case
    # a deployment ever needs to run more than one HF model concurrently.
    _MODEL_CACHE: ClassVar[Dict[str, object]] = {}

    def __init__(self, settings: EmbeddingSettings) -> None:
        self._settings = settings
        self._model_name = settings.HUGGINGFACE_MODEL
        self._model: Optional[object] = None
        self._load_error: Optional[str] = None
        self._try_load_model()

    def _try_load_model(self) -> None:
        """
        Attempts to load the sentence-transformers model immediately so
        `is_configured()` reflects real readiness rather than optimistically
        assuming success. Any failure (missing package, bad model name, no
        internet on first download) is captured, logged, and surfaced via
        `is_configured() == False` instead of crashing the whole app.
        """
        if self._model_name in self._MODEL_CACHE:
            self._model = self._MODEL_CACHE[self._model_name]
            return

        try:
            from sentence_transformers import SentenceTransformer

            logger.info("Loading HuggingFace model '%s' (first use, may take a moment)...", self._model_name)
            model = SentenceTransformer(self._model_name)
            self._MODEL_CACHE[self._model_name] = model
            self._model = model
            logger.info("HuggingFace model '%s' loaded successfully.", self._model_name)
        except Exception as exc:  # noqa: BLE001
            self._load_error = str(exc)
            logger.error("Failed to load HuggingFace model '%s': %s", self._model_name, exc)

    @property
    def provider_name(self) -> str:
        return "huggingface"

    @property
    def model_name(self) -> str:
        return self._model_name

    @property
    def dimension(self) -> int:
        if self._model is not None:
            return int(self._model.get_sentence_embedding_dimension())  # type: ignore[attr-defined]
        return 384  # all-MiniLM-L6-v2's known dimension, used as a sane default before load

    def is_configured(self) -> bool:
        return self._model is not None

    async def embed_batch(self, texts: List[str]) -> List[List[float]]:
        import asyncio

        if not self.is_configured():
            raise EmbeddingProviderError(
                self.provider_name, self._load_error or "Model failed to load."
            )

        try:
            return await asyncio.to_thread(self._embed_batch_sync, texts)
        except EmbeddingProviderError:
            raise
        except Exception as exc:  # noqa: BLE001
            logger.error("HuggingFace embedding failed: %s", exc)
            raise EmbeddingProviderError(self.provider_name, reason=str(exc)) from exc

    def _embed_batch_sync(self, texts: List[str]) -> List[List[float]]:
        vectors = self._model.encode(  # type: ignore[union-attr]
            texts,
            batch_size=min(len(texts), 64),
            show_progress_bar=False,
            convert_to_numpy=True,
        )
        return vectors.tolist()
