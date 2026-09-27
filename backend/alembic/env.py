"""Alembic environment.

Two decisions worth stating:

* **The database URL comes from application settings**, not from
  ``alembic.ini``. There is exactly one place a connection string is defined
  and no credential is ever committed. Override for one run with
  ``alembic -x url=postgresql://... upgrade head``.

* **Migrations run through the same asyncpg driver as the application** using
  Alembic's async support. Introducing a second driver purely for DDL would
  mean two things that can disagree about the connection, and a production
  migration that behaves differently from local is a bad trade.

``compare_type`` and ``compare_server_default`` are enabled so autogenerate
produces honest diffs for enum and default changes instead of letting the
schema quietly drift.

There is deliberately **no custom ``render_item`` hook**. Alembic already emits
``CREATE TYPE`` with ``checkfirst=True``, and supplying a ``render_item``
callback switches table rendering to a path where returning ``None`` yields an
empty ``op.create_table()`` - a silently column-less migration. Enum DDL
therefore stays on Alembic's own, tested path.
"""

from __future__ import annotations

import asyncio
import os
import sys
from logging.config import fileConfig
from pathlib import Path

from alembic import context
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

# Make the application package importable when alembic runs from backend/.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import app.models  # noqa: F401  (registers every table on Base.metadata)
from app.core.config import get_settings
from app.db.base import Base

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def _database_url() -> str:
    """Resolve the URL, normalising a bare postgres URL for asyncpg."""
    x_args = context.get_x_argument(as_dictionary=True)
    url = x_args.get("url") or os.getenv("DATABASE_URL_OVERRIDE")
    if not url:
        url = get_settings().effective_database_url
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql+asyncpg://", 1)
    elif url.startswith("postgresql://"):
        url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
    if url.startswith("postgresql://"):
        url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
    return url


def _do_run_migrations(connection: Connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
        compare_server_default=True,
        include_schemas=False,
        literal_binds=False,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


async def _run_async_migrations() -> None:
    section = config.get_section(config.config_ini_section) or {}
    section["sqlalchemy.url"] = _database_url()
    connectable = async_engine_from_config(section, prefix="sqlalchemy.", poolclass=pool.NullPool)
    async with connectable.connect() as connection:
        await connection.run_sync(_do_run_migrations)
    await connectable.dispose()


def _run_migrations_offline() -> None:
    """Emit SQL to stdout without connecting (``alembic upgrade head --sql``)."""
    context.configure(
        url=_database_url().replace("+asyncpg", ""),
        target_metadata=target_metadata,
        compare_type=True,
        compare_server_default=True,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


if context.is_offline_mode():
    _run_migrations_offline()
else:
    asyncio.run(_run_async_migrations())
