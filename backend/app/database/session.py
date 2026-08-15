"""
app/database/session.py

FastAPI dependency for obtaining a request-scoped DB session.

Usage in a route or service:

    from app.database.session import get_db

    async def some_route(db: AsyncSession = Depends(get_db)):
        ...
"""

from __future__ import annotations

from typing import AsyncIterator

from sqlalchemy.ext.asyncio import AsyncSession

from app.database.database import get_session


async def get_db() -> AsyncIterator[AsyncSession]:
    """Thin re-export as a dedicated dependency — keeps `Depends(get_db)` call sites
    decoupled from where the engine/sessionmaker actually live."""
    async for session in get_session():
        yield session
