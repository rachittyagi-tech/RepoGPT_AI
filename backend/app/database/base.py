"""
app/database/base.py

The single SQLAlchemy `DeclarativeBase` shared by every ORM model in the
app. Alembic's `env.py` imports `Base.metadata` from here to autogenerate
migrations — every model module MUST be imported somewhere reachable from
that import chain (see `app/models/__init__.py`) or Alembic won't see it.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, MetaData
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

# Explicit naming convention for constraints/indexes — without this,
# Alembic autogenerates unpredictable constraint names, which makes
# `alembic downgrade` and manual migration edits painful later.
NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    """Base class for all ORM models."""

    metadata = MetaData(naming_convention=NAMING_CONVENTION)


class UUIDPrimaryKeyMixin:
    """Adds a UUID primary key (`id`), generated server-side by Python (uuid4)."""

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True
    )


class TimestampMixin:
    """Adds `created_at` / `updated_at`, both timezone-aware UTC."""

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
