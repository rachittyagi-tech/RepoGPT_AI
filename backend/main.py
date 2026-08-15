"""
main.py

RepoGPT AI — Backend Application Entrypoint (Step 2).

Responsibilities of this file ONLY:
    - Construct the FastAPI app instance
    - Wire up configuration, logging, middleware, exception handlers
    - Register routers
    - Define the startup/shutdown lifespan

Business logic never lives here — see app/services/, app/api/, etc.

Run locally:
    uvicorn main:app --reload --host 0.0.0.0 --port 8000

Run via Docker:
    docker-compose up backend
"""

from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import AsyncIterator

from fastapi import FastAPI, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.analytics import router as analytics_router
from app.api.auth import router as auth_router
from app.api.chat import router as chat_router
from app.api.chunking import router as chunking_router
from app.api.embeddings import router as embeddings_router
from app.api.github import router as github_router
from app.api.intelligence import router as intelligence_router
from app.api.rag import router as rag_router
from app.api.scanner import router as scanner_router
from app.api.users import router as users_router
from app.api.v1.router import api_router
from app.api.vector_store import router as vector_store_router
from app.core.config import APP_METADATA, CORS_CONFIG
from app.core.exceptions import register_exception_handlers
from app.core.logging import get_logger, setup_logging
from app.core.settings import settings
from app.middleware.middleware import register_middlewares

logger = get_logger("main")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """
    Application lifespan handler — replaces the deprecated
    `@app.on_event("startup"/"shutdown")` decorators (FastAPI's
    recommended approach since 0.93+).

    Code before `yield` runs on STARTUP.
    Code after `yield` runs on SHUTDOWN.
    """
    # ---------------- Startup ----------------
    setup_logging()
    logger.info("=" * 60)
    logger.info("Starting %s v%s [%s]", settings.APP_NAME, settings.APP_VERSION, settings.APP_ENV)
    logger.info("Startup time: %s", datetime.now(timezone.utc).isoformat())
    logger.info("Debug mode: %s", settings.APP_DEBUG)
    logger.info("=" * 60)

    # PostgreSQL (Step 11 — Auth & User Management). The async engine itself
    # is created eagerly at import time in `app.database.database` (module
    # singleton, same pattern as `ChromaDBClient`); here we just verify
    # connectivity so a misconfigured DATABASE_URL fails fast at startup
    # instead of on the first request.
    from app.database.database import check_database_connection, engine

    if await check_database_connection():
        logger.info("PostgreSQL connection OK.")
    else:
        logger.warning(
            "PostgreSQL connection check FAILED — auth/user endpoints will error "
            "until DATABASE_URL is reachable. Run `docker-compose up db` or check "
            "your .env."
        )

    # Placeholders for future steps — Redis, ChromaDB clients, etc.
    # will be initialized here and attached to `app.state` as needed.

    yield  # ---- application runs here ----

    # ---------------- Shutdown ----------------
    logger.info("Shutting down %s ...", settings.APP_NAME)
    await engine.dispose()
    logger.info("Shutdown complete.")


def create_app() -> FastAPI:
    """
    Application factory. Using a factory function (rather than a bare
    module-level `app = FastAPI()`) makes the app easier to instantiate
    multiple times in tests with different overrides.
    """
    app = FastAPI(lifespan=lifespan, **APP_METADATA)

    # ---- Middleware (order matters — see app/middleware/middleware.py) ----
    app.add_middleware(CORSMiddleware, **CORS_CONFIG)
    register_middlewares(app)

    # ---- Global exception handlers ----
    register_exception_handlers(app)

    # ---- Routers ----
    app.include_router(api_router, prefix=settings.API_V1_PREFIX)

    # Authentication & User Management module (Step 11). Mounted at
    # /api/auth and /api/users, matching the flat, module-scoped prefix
    # style already used by the GitHub/Scanner/etc. modules below rather
    # than nesting under /api/v1 — these will graduate together in a
    # future versioning pass.
    app.include_router(auth_router, prefix="/api/auth")
    app.include_router(users_router, prefix="/api/users")

    # GitHub Repository Management module (Step 3). Mounted at the exact
    # /api/github prefix specified for this module, separate from the
    # /api/v1 versioned router — this module will likely graduate into
    # /api/v1/github once the versioned contract stabilizes.
    app.include_router(github_router, prefix="/api/github")

    # Repository Scanner & File Processing module (Step 4). Depends on
    # repositories already cloned by the GitHub module above.
    app.include_router(scanner_router, prefix="/api/scanner")

    # Code Processing Pipeline module (Step 5). Depends on a repository
    # already scanned by the Scanner module above.
    app.include_router(chunking_router, prefix="/api/chunking")

    # Embedding Generation Layer module (Step 6). Depends on a repository
    # already chunked by the Chunking module above.
    app.include_router(embeddings_router, prefix="/api/embeddings")

    # ChromaDB Vector Store Layer module (Step 7). Depends on a repository
    # already embedded by the Embeddings module above.
    app.include_router(vector_store_router, prefix="/api/vector")

    # RAG Pipeline module (Step 8). Depends on a repository already
    # indexed by the Vector Store module above.
    app.include_router(rag_router, prefix="/api/rag")

    # AI Chat Engine module (Step 9). Uses the RAG Pipeline module above
    # to ground Gemini's answers in actual repository content.
    app.include_router(chat_router, prefix="/api/chat")

    # Repository Analytics & AI Insights Dashboard module (Step 12).
    # Read-only views over data already produced by every module above —
    # does not trigger scan/chunk/embed/index runs itself.
    app.include_router(analytics_router, prefix="/api/analytics")

    # AI Code Intelligence Engine module (Step 13). Uses RAG (Step 8) +
    # Gemini for AI-reasoning endpoints, plus fast LLM-free heuristic
    # scanners for GET /quality — see app/services/quality_score_service.py.
    app.include_router(intelligence_router, prefix="/api/intelligence")

    # ---- Root endpoint (unversioned, outside api_router by design) ----
    @app.get("/", tags=["Root"], summary="Service root")
    async def root() -> dict:
        """Basic root endpoint confirming the service is reachable."""
        return {
            "service": settings.APP_NAME,
            "status": "ok",
            "version": settings.APP_VERSION,
            "docs": "/docs" if not settings.is_production else "disabled in production",
            "api_prefix": settings.API_V1_PREFIX,
        }

    @app.get("/health", tags=["Root"], summary="Liveness probe (Docker/load balancer)")
    async def liveness() -> dict:
        """
        Unversioned, dependency-free liveness check (Step 14) — used by the
        Docker `HEALTHCHECK` directive and load balancers. Deliberately does
        NOT check the database/ChromaDB: a liveness probe should only ever
        answer "is this process able to serve requests at all", so a slow
        or temporarily-down dependency doesn't trigger a container restart
        loop. For dependency checks, see `GET /api/health`.
        """
        return {"status": "alive", "service": settings.APP_NAME, "version": settings.APP_VERSION}

    @app.get("/api/health", tags=["Root"], summary="Readiness probe — backend, database, ChromaDB, config")
    async def readiness() -> JSONResponse:
        """
        Comprehensive readiness check (Step 14): verifies the backend process,
        PostgreSQL connectivity, ChromaDB persistence, and basic application
        configuration — WITHOUT exposing any secret values, only booleans.
        Returns HTTP 503 (rather than 200) when any critical component is
        down, so orchestrators correctly stop routing traffic to this instance.
        """
        from app.database.chromadb_client import ChromaDBClient
        from app.database.database import check_database_connection

        database_ok = await check_database_connection()

        try:
            ChromaDBClient.get_instance().list_collection_names()
            chromadb_ok = True
        except Exception:  # noqa: BLE001 — any failure means "not ready", detail is logged internally
            logger.warning("ChromaDB readiness check failed", exc_info=True)
            chromadb_ok = False

        config_ok = bool(settings.SECRET_KEY) and settings.SECRET_KEY != "dev-secret-change-me" if settings.is_production else True

        components = {"database": database_ok, "chromadb": chromadb_ok, "configuration": config_ok}
        overall_ok = all(components.values())

        return JSONResponse(
            status_code=status.HTTP_200_OK if overall_ok else status.HTTP_503_SERVICE_UNAVAILABLE,
            content={
                "status": "healthy" if overall_ok else "degraded",
                "service": settings.APP_NAME,
                "version": settings.APP_VERSION,
                "environment": settings.APP_ENV,
                "components": components,
            },
        )

    return app


app = create_app()
