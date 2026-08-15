"""
app/database/database.py

Constructs the process-wide async SQLAlchemy engine + session factory for
PostgreSQL. Mirrors the singleton pattern already used by
`app.database.chromadb_client.ChromaDBClient` for consistency.

Nothing outside this module (and `app.database.session`) should import
`create_async_engine` or `AsyncSession` directly — everyone else consumes
the `get_db` dependency from `app.database.session`.
"""

from __future__ import annotations

from typing import AsyncIterator

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

from app.core.logging import get_logger
from app.core.settings import settings

logger = get_logger("database.database")

# `pool_pre_ping` avoids serving stale/dead connections after DB restarts
# or long idle periods (common in dev, and after cloud-DB failovers in prod).
engine: AsyncEngine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.APP_DEBUG and not settings.is_production,
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20,
)

AsyncSessionLocal: async_sessionmaker[AsyncSession] = async_sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False,
    expire_on_commit=False,
)


async def get_session() -> AsyncIterator[AsyncSession]:
    """
    Yields a scoped `AsyncSession`, committing on success and rolling back
    on any exception. Wrapped by the FastAPI dependency in
    `app.database.session.get_db`.
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def check_database_connection() -> bool:
    """Lightweight connectivity check, used by the health/system endpoints."""
    from sqlalchemy import text

    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        return True
    except Exception as exc:  # noqa: BLE001 — deliberately broad for a health probe
        logger.error("Database connectivity check failed: %s", exc)
        return False
