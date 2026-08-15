"""
app/core/logging.py

Structured logging setup for RepoGPT AI.

- Uses Python's standard `logging` module (no extra dependency needed for
  Step 2) configured via `dictConfig` from `app.core.config.LOGGING_CONFIG`.
- Provides `get_logger(name)` so every module gets a properly namespaced
  logger, e.g. `repogpt.services.chat`.
- Supports an optional JSON formatter (toggled by `LOG_JSON=true` in .env)
  for production log-aggregator compatibility (ELK, CloudWatch, etc).
"""

import json
import logging
import logging.config
import sys
from datetime import datetime, timezone
from typing import Any, Dict

from app.core.config import LOGGING_CONFIG
from app.core.settings import settings

LOGGER_NAMESPACE = "repogpt"


class JSONFormatter(logging.Formatter):
    """Renders each log record as a single-line JSON object."""

    def format(self, record: logging.LogRecord) -> str:
        payload: Dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "line": record.lineno,
        }
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)

        # Allow callers to attach extra structured fields, e.g.
        # logger.info("event", extra={"request_id": "..."})
        for key in ("request_id", "path", "method", "status_code", "duration_ms"):
            if hasattr(record, key):
                payload[key] = getattr(record, key)

        return json.dumps(payload, default=str)


def setup_logging() -> None:
    """
    Initializes application-wide logging.

    Called once during application startup (see app.core.lifespan).
    """
    if settings.LOG_JSON:
        handler = logging.StreamHandler(stream=sys.stdout)
        handler.setFormatter(JSONFormatter())
        root_logger = logging.getLogger()
        root_logger.handlers = [handler]
        root_logger.setLevel(settings.LOG_LEVEL)
    else:
        logging.config.dictConfig(LOGGING_CONFIG)

    logger = get_logger("core.logging")
    logger.info(
        "Logging initialized | env=%s | level=%s | json=%s",
        settings.APP_ENV,
        settings.LOG_LEVEL,
        settings.LOG_JSON,
    )


def get_logger(name: str) -> logging.Logger:
    """
    Returns a namespaced logger, e.g. get_logger("services.chat") ->
    logger name "repogpt.services.chat".
    """
    return logging.getLogger(f"{LOGGER_NAMESPACE}.{name}")
