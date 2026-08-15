"""
app/services/gemini_service.py

Wraps Google Gemini's generative API for chat completion — both
non-streaming (`generate`) and streaming (`generate_stream`).

Extensibility note ("Support Future LLM Providers"): `ChatService` only
calls this class's three public methods (`is_configured`, `generate`,
`generate_stream`). A future `OpenAIService`/`ClaudeService` implementing
the same three methods could be swapped in via `ChatService`'s
constructor without changing any orchestration logic — this narrow
surface IS the extension point, kept intentionally small rather than
introducing a formal ABC for a single current implementation.

The google-generativeai SDK is synchronous; `generate` wraps it in
`asyncio.to_thread` (same pattern as Step 6's embedding providers).
`generate_stream` bridges the SDK's synchronous streaming iterator into
an async generator using a background thread + `asyncio.Queue`, since
`to_thread` alone can't yield progressively.
"""

from __future__ import annotations

import asyncio
import threading
from typing import Any, AsyncIterator, Optional, Tuple

from app.core.exceptions import (
    ChatProviderAuthError,
    ChatProviderError,
    ChatProviderNotConfiguredError,
    ChatRateLimitError,
    ChatTimeoutError,
)
from app.core.gemini_config import GeminiChatSettings, get_gemini_chat_settings
from app.core.logging import get_logger
from app.schemas.chat import TokenUsage

logger = get_logger("services.gemini")

_PROVIDER_NAME = "gemini"
_AUTH_MARKERS = ("api key", "unauthorized", "permission denied", "invalid api key")
_RATE_LIMIT_MARKERS = ("quota", "rate limit", "resource exhausted", "429")


class GeminiService:
    """Generates chat completions (streaming + non-streaming) using Google Gemini."""

    def __init__(self, settings: Optional[GeminiChatSettings] = None) -> None:
        self.settings = settings or get_gemini_chat_settings()
        self._configured = bool(self.settings.GEMINI_API_KEY)
        self._model: Optional[Any] = None

        if self._configured:
            self._configure_client()

    def _configure_client(self) -> None:
        """Lazily imports and configures the SDK — avoids a hard import-time dependency."""
        import google.generativeai as genai

        genai.configure(api_key=self.settings.GEMINI_API_KEY)
        self._model = genai.GenerativeModel(
            model_name=self.settings.GEMINI_MODEL,
            generation_config={
                "max_output_tokens": self.settings.MAX_OUTPUT_TOKENS,
                "temperature": self.settings.TEMPERATURE,
                "top_p": self.settings.TOP_P,
                "top_k": self.settings.TOP_K,
            },
        )

    def is_configured(self) -> bool:
        return self._configured and self._model is not None

    @property
    def model_name(self) -> str:
        return self.settings.GEMINI_MODEL

    # ------------------------------------------------------------------
    # Non-streaming
    # ------------------------------------------------------------------
    async def generate(self, prompt: str) -> Tuple[str, TokenUsage]:
        """
        Generates a full response for `prompt`, with retry-with-backoff +
        per-attempt timeout (same policy shape as Step 6's embedding
        providers). Returns `(answer_text, token_usage)`.
        """
        if not self.is_configured():
            raise ChatProviderNotConfiguredError(_PROVIDER_NAME, "Missing GEMINI_API_KEY.")

        max_attempts = self.settings.MAX_RETRIES + 1
        last_exc: Exception = ChatProviderError(_PROVIDER_NAME, "Unknown failure.")

        for attempt in range(1, max_attempts + 1):
            try:
                return await asyncio.wait_for(
                    asyncio.to_thread(self._generate_sync, prompt),
                    timeout=self.settings.REQUEST_TIMEOUT,
                )
            except ChatProviderAuthError:
                raise
            except asyncio.TimeoutError:
                last_exc = ChatTimeoutError(_PROVIDER_NAME, self.settings.REQUEST_TIMEOUT)
            except (ChatRateLimitError, ChatProviderError) as exc:
                last_exc = exc

            if attempt < max_attempts:
                backoff_seconds = 2 ** (attempt - 1)
                logger.warning(
                    "Gemini generate attempt %d/%d failed (%s) — retrying in %ds...",
                    attempt,
                    max_attempts,
                    last_exc,
                    backoff_seconds,
                )
                await asyncio.sleep(backoff_seconds)

        raise last_exc

    def _generate_sync(self, prompt: str) -> Tuple[str, TokenUsage]:
        try:
            response = self._model.generate_content(prompt)  # type: ignore[union-attr]
        except Exception as exc:  # noqa: BLE001
            raise self._classify_error(exc) from exc

        text = getattr(response, "text", "") or ""
        usage = self._extract_usage(response, prompt, text)
        return text, usage

    # ------------------------------------------------------------------
    # Streaming
    # ------------------------------------------------------------------
    async def generate_stream(self, prompt: str) -> AsyncIterator[str]:
        """
        Yields the response text incrementally as Gemini generates it.

        Bridges the SDK's synchronous streaming iterator to async by
        running it in a background thread and relaying chunks through an
        `asyncio.Queue` — `asyncio.to_thread` alone can only await a
        single return value, not a progressive stream.
        """
        if not self.is_configured():
            raise ChatProviderNotConfiguredError(_PROVIDER_NAME, "Missing GEMINI_API_KEY.")

        queue: "asyncio.Queue[Any]" = asyncio.Queue()
        loop = asyncio.get_event_loop()

        def producer() -> None:
            try:
                for chunk in self._model.generate_content(prompt, stream=True):  # type: ignore[union-attr]
                    text = getattr(chunk, "text", "") or ""
                    if text:
                        loop.call_soon_threadsafe(queue.put_nowait, text)
            except Exception as exc:  # noqa: BLE001
                classified = self._classify_error(exc)
                loop.call_soon_threadsafe(queue.put_nowait, classified)
            finally:
                loop.call_soon_threadsafe(queue.put_nowait, None)

        threading.Thread(target=producer, daemon=True, name="gemini-stream-producer").start()

        while True:
            item = await queue.get()
            if item is None:
                break
            if isinstance(item, Exception):
                raise item
            yield item

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _extract_usage(self, response: Any, prompt: str, completion: str) -> TokenUsage:
        usage_metadata = getattr(response, "usage_metadata", None)
        if usage_metadata is not None:
            return TokenUsage(
                prompt_tokens=getattr(usage_metadata, "prompt_token_count", 0) or 0,
                completion_tokens=getattr(usage_metadata, "candidates_token_count", 0) or 0,
                total_tokens=getattr(usage_metadata, "total_token_count", 0) or 0,
            )

        # Fallback if the SDK response doesn't include usage metadata —
        # reuses Step 8's tiktoken-based estimator (model-agnostic).
        from app.services.context_builder import estimate_tokens

        prompt_tokens = estimate_tokens(prompt)
        completion_tokens = estimate_tokens(completion)
        logger.debug("Gemini response missing usage_metadata — using token estimate fallback.")
        return TokenUsage(
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=prompt_tokens + completion_tokens,
        )

    def _classify_error(self, exc: Exception) -> Exception:
        message = str(exc).lower()

        if any(marker in message for marker in _AUTH_MARKERS):
            logger.warning("Gemini auth failure: %s", exc)
            return ChatProviderAuthError(_PROVIDER_NAME)

        if any(marker in message for marker in _RATE_LIMIT_MARKERS):
            logger.warning("Gemini rate limited: %s", exc)
            return ChatRateLimitError(_PROVIDER_NAME)

        logger.error("Gemini provider error: %s", exc)
        return ChatProviderError(_PROVIDER_NAME, reason=str(exc))


def get_gemini_service() -> GeminiService:
    """FastAPI dependency provider — see app/services/chat_service.py."""
    return GeminiService()
