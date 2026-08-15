"""
app/middleware/rate_limit.py

Lightweight, dependency-free rate limiting (Step 15) for RepoGPT AI's most
expensive/abusable endpoints: repository cloning, the scan/chunk/embed/index
pipeline, chat (each turn calls Gemini), the AI Code Intelligence endpoints
(each also calls Gemini), and auth (brute-force protection on login/register).

Design:
    - Pure in-memory sliding window, keyed by client IP + a per-limiter
      bucket name. No new dependency (no slowapi/Redis) — appropriate for
      the current single-instance deployment (see docker-compose.prod.yml,
      Step 14). Deliberately documented as NOT correct across multiple
      backend replicas — a real multi-instance deployment needs a shared
      store (Redis) for this to work correctly; swap `_HITS` for a Redis
      sorted-set implementation behind the same `RateLimiter` interface
      when that's actually needed.
    - Exposed as a FastAPI dependency factory (`rate_limit(...)`), applied
      per-router via `APIRouter(dependencies=[Depends(rate_limit(...))])`
      — additive, doesn't require any frontend change, so it's safe to
      enable without touching working flows.
"""

from __future__ import annotations

import time
from collections import defaultdict
from typing import ClassVar, Dict, List

from fastapi import Request

from app.core.exceptions import AppError
from app.core.logging import get_logger

logger = get_logger("middleware.rate_limit")


class RateLimitExceededError(AppError):
    """429 — too many requests from this client for this endpoint group."""

    status_code = 429
    error_code = "rate_limit_exceeded"

    def __init__(self, retry_after_seconds: int) -> None:
        self.retry_after_seconds = retry_after_seconds
        super().__init__(
            f"Too many requests. Please retry after {retry_after_seconds} second(s).",
            retry_after_seconds=retry_after_seconds,
        )


class _SlidingWindowLimiter:
    """Process-wide (class-level) sliding-window hit tracker — same in-memory,
    class-level cache pattern used throughout this codebase (Scanner/Chunking/
    Embedding services' own `_CACHE` dicts)."""

    _HITS: ClassVar[Dict[str, List[float]]] = defaultdict(list)

    @classmethod
    def check(cls, key: str, max_requests: int, window_seconds: int) -> None:
        now = time.monotonic()
        window_start = now - window_seconds

        hits = cls._HITS[key]
        # Drop expired timestamps — keeps memory bounded without a background sweep.
        while hits and hits[0] < window_start:
            hits.pop(0)

        if len(hits) >= max_requests:
            retry_after = max(1, int(window_seconds - (now - hits[0])))
            raise RateLimitExceededError(retry_after)

        hits.append(now)


def _client_key(request: Request) -> str:
    """Best-effort client identity: honors X-Forwarded-For (set by Nginx in
    production, see frontend/nginx.conf) since `request.client.host` would
    otherwise always be the proxy's own IP once behind Nginx."""
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def rate_limit(bucket: str, max_requests: int, window_seconds: int):
    """
    FastAPI dependency factory. Usage:

        router = APIRouter(dependencies=[Depends(rate_limit("chat", 20, 60))])

    Raises `RateLimitExceededError` (-> HTTP 429, via the standard AppError
    handler in app/core/exceptions.py) once `max_requests` is exceeded
    within any rolling `window_seconds` window, per client IP.
    """

    async def _dependency(request: Request) -> None:
        key = f"{bucket}:{_client_key(request)}"
        _SlidingWindowLimiter.check(key, max_requests, window_seconds)

    return _dependency
