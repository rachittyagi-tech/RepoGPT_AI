"""
app/providers/base_embedding.py

Abstract provider interface for embedding generation (Strategy pattern).

Every concrete provider (Gemini, HuggingFace today; OpenAI, Voyage AI,
Jina AI, Azure OpenAI in future steps) implements this exact contract.
`EmbeddingService` only ever talks to `BaseEmbeddingProvider` — it never
imports a concrete provider class directly — so switching providers is
purely an `EMBEDDING_PROVIDER` config change, never a business-logic
change (Open/Closed + Dependency Inversion).

Cross-cutting concerns (retry, per-batch timeout, structured logging,
metrics) live in `EmbeddingService`, NOT in individual providers — this
keeps every provider implementation small and avoids duplicating that
logic across Gemini/HuggingFace/OpenAI/etc. (DRY). Providers are only
responsible for: (1) calling their SDK/API, (2) classifying failures
into the standard exceptions below.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import List


class BaseEmbeddingProvider(ABC):
    """Contract every embedding provider must implement."""

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Short machine-readable identifier, e.g. 'gemini', 'huggingface'."""

    @property
    @abstractmethod
    def model_name(self) -> str:
        """The specific model in use, e.g. 'text-embedding-004'."""

    @property
    @abstractmethod
    def dimension(self) -> int:
        """Vector dimensionality produced by this provider/model."""

    @abstractmethod
    def is_configured(self) -> bool:
        """True if this provider has everything it needs to run (API key present, model loadable, etc.)."""

    @abstractmethod
    async def embed_batch(self, texts: List[str]) -> List[List[float]]:
        """
        Embeds a batch of texts, returning one vector per input text in
        the same order as `texts`.

        Implementations MUST raise one of the standard exceptions from
        `app.core.exceptions` on failure (EmbeddingAuthError,
        EmbeddingRateLimitError, EmbeddingProviderError) rather than
        letting raw SDK exceptions propagate — this is what lets
        `EmbeddingService` apply one generic retry/classification policy
        across every provider.
        """
