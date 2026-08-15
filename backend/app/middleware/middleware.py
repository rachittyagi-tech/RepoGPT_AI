"""
app/middleware/middleware.py

Custom ASGI middleware for RepoGPT AI.

Contains:
- `RequestContextMiddleware` — assigns a unique request ID to every
  incoming request (propagated via response header + log records) and
  measures request duration.
- `RequestLoggingMiddleware` — structured access-log entry per request
  (method, path, status code, duration), independent of Uvicorn's own
  access log so we control the format/fields.

Both middlewares are plain ASGI/Starlette `BaseHTTPMiddleware` subclasses,
registered in `main.py`. Keeping them in their own module (separate from
`core/`) follows Single Responsibility: `core/` holds config/logging/
exceptions, `middleware/` holds request-pipeline concerns only.
"""

from __future__ import annotations

import time
import uuid
from typing import Callable

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

from app.core.config import PROCESS_TIME_HEADER, REQUEST_ID_HEADER
from app.core.logging import get_logger

logger = get_logger("middleware")


class RequestContextMiddleware(BaseHTTPMiddleware):
    """
    Attaches a unique `request_id` to `request.state` (used by exception
    handlers for traceability) and echoes it back as a response header so
    clients/logs can correlate a request end-to-end.
    """

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        request_id = request.headers.get(REQUEST_ID_HEADER, str(uuid.uuid4()))
        request.state.request_id = request_id

        response = await call_next(request)
        response.headers[REQUEST_ID_HEADER] = request_id
        return response


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """
    Logs one structured line per request:
        method, path, status_code, duration_ms, request_id

    Also attaches the `X-Process-Time` header to every response, useful for
    quick performance debugging without needing a full APM tool yet.
    """

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        start_time = time.perf_counter()
        request_id = getattr(request.state, "request_id", "unknown")

        try:
            response = await call_next(request)
        except Exception:
            duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
            logger.exception(
                "Request failed | method=%s path=%s duration_ms=%s request_id=%s",
                request.method,
                request.url.path,
                duration_ms,
                request_id,
                extra={
                    "request_id": request_id,
                    "method": request.method,
                    "path": request.url.path,
                    "duration_ms": duration_ms,
                },
            )
            raise

        duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
        response.headers[PROCESS_TIME_HEADER] = str(duration_ms)

        logger.info(
            "Request completed | method=%s path=%s status_code=%s duration_ms=%s request_id=%s",
            request.method,
            request.url.path,
            response.status_code,
            duration_ms,
            request_id,
            extra={
                "request_id": request_id,
                "method": request.method,
                "path": request.url.path,
                "status_code": response.status_code,
                "duration_ms": duration_ms,
            },
        )
        return response


def register_middlewares(app) -> None:  # type: ignore[no-untyped-def]
    """
    Registers custom middleware on the FastAPI app, in execution order.

    Note: Starlette executes middleware in reverse registration order for
    the request path, so `RequestContextMiddleware` (which must run first
    to generate the request_id) is added LAST here to end up outermost.
    """
    app.add_middleware(RequestLoggingMiddleware)
    app.add_middleware(RequestContextMiddleware)
