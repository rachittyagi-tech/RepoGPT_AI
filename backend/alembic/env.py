"""
alembic/env.py

Wires Alembic to:
    1. The app's own settings (`app.core.settings.settings.DATABASE_URL`),
       so the DB URL lives in exactly one place (.env), never duplicated
       in alembic.ini.
    2. `Base.metadata` (via `app.models`, which imports every model) so
       `alembic revision --autogenerate` can diff against the real schema.

Uses an async engine (`asyncpg`) via `run_sync`, matching the app's own
async SQLAlchemy setup in `app.database.database`.
"""

from __future__ import annotations

import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

# Import every ORM model so Base.metadata is fully populated before Alembic
# inspects it — see app/models/__init__.py.
from app.database.base import Base
from app.core.settings import settings
import app.models  # noqa: F401

config = context.config
config.set_main_option("sqlalchemy.url", settings.DATABASE_URL)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Generates SQL scripts without a live DB connection (`alembic upgrade --sql`)."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata, compare_type=True)
    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    """Runs migrations against a live DB using the app's async engine config."""
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
