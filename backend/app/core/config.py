"""
app/core/config.py

While `settings.py` defines and validates *environment-driven* configuration
(Pydantic `BaseSettings`), this module holds *derived* and *static*
application configuration built on top of it — metadata for the OpenAPI
docs, the logging dict-config, and other cross-cutting constants that
depend on `settings` but shouldn't live inside the settings model itself.

Keeping this separate from `settings.py` follows Single Responsibility:
- settings.py  → "what are the values, and are they valid?"
- config.py    → "how do we use those values to configure the app?"
"""

from typing import Any, Dict

from app.core.settings import settings

# ---------------------------------------------------------------------------
# OpenAPI / FastAPI application metadata
# ---------------------------------------------------------------------------
APP_METADATA: Dict[str, Any] = {
    "title": settings.APP_NAME,
    "description": (
        "RepoGPT AI — Intelligent GitHub Repository Chat & Code Analysis "
        "Platform. Backend foundation (Step 2): core app, config, logging, "
        "middleware, and exception handling."
    ),
    "version": settings.APP_VERSION,
    "docs_url": "/docs" if not settings.is_production else None,
    "redoc_url": "/redoc" if not settings.is_production else None,
    "openapi_url": "/openapi.json" if not settings.is_production else None,
}

# ---------------------------------------------------------------------------
# CORS configuration
# ---------------------------------------------------------------------------
CORS_CONFIG: Dict[str, Any] = {
    "allow_origins": settings.cors_origins,
    "allow_credentials": True,
    "allow_methods": ["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    "allow_headers": ["*"],
}

# ---------------------------------------------------------------------------
# Logging dict-config (consumed by app.core.logging)
# ---------------------------------------------------------------------------
LOG_FORMAT_TEXT = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
LOG_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

LOGGING_CONFIG: Dict[str, Any] = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "default": {
            "format": LOG_FORMAT_TEXT,
            "datefmt": LOG_DATE_FORMAT,
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "default",
            "level": settings.LOG_LEVEL,
        },
    },
    "root": {
        "handlers": ["console"],
        "level": settings.LOG_LEVEL,
    },
    "loggers": {
        "uvicorn": {"handlers": ["console"], "level": settings.LOG_LEVEL, "propagate": False},
        "uvicorn.error": {"handlers": ["console"], "level": settings.LOG_LEVEL, "propagate": False},
        "uvicorn.access": {"handlers": ["console"], "level": "WARNING", "propagate": False},
        "repogpt": {"handlers": ["console"], "level": settings.LOG_LEVEL, "propagate": False},
    },
}

# ---------------------------------------------------------------------------
# Misc application-wide constants
# ---------------------------------------------------------------------------
REQUEST_ID_HEADER = "X-Request-ID"
PROCESS_TIME_HEADER = "X-Process-Time"
