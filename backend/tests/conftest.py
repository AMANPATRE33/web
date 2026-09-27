"""Shared pytest fixtures.

Database-backed tests need a real PostgreSQL, because the guarantees being
tested (generated columns, partial unique indexes, ``SELECT ... FOR UPDATE``
serialisation, check constraints) are *database* guarantees. SQLite would
silently pass tests that do not describe the production system.

The test database is derived from ``DATABASE_URL`` with the database name
replaced by ``storefront_test``, so running the suite can never touch
development data. It is created if missing and migrated once per session.

When ``TEST_DATABASE_URL`` is unset **and** no database is reachable, the
database-backed fixtures skip with an explicit message rather than failing, so
``pytest tests/unit`` works on a machine with no infrastructure at all.
"""

from __future__ import annotations

import os
import subprocess
import sys
import uuid
from collections.abc import AsyncGenerator, Iterator
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

import app.models  # noqa: F401  (ensures metadata is fully populated)
import pytest
from app.core.config import get_settings
from app.db.base import Base
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

BACKEND_DIR = Path(__file__).resolve().parents[1]
DEFAULT_TEST_DB_NAME = "storefront_test"


# ---------------------------------------------------------------------------
# URL helpers
# ---------------------------------------------------------------------------
def _test_database_url() -> str | None:
    explicit = os.getenv("TEST_DATABASE_URL")
    if explicit:
        return _normalise(explicit)

    try:
        base = get_settings().effective_database_url
    except Exception:
        return None

    parts = urlsplit(base)
    name = DEFAULT_TEST_DB_NAME
    return urlunsplit(parts._replace(path=f"/{name}"))


def _normalise(url: str) -> str:
    if url.startswith("postgres://"):
        return url.replace("postgres://", "postgresql+asyncpg://", 1)
    if url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+asyncpg://", 1)
    return url


def _admin_database_url() -> str | None:
    """Connection URL pointing at the ``postgres`` maintenance database."""
    url = _test_database_url()
    if not url:
        return None
    parts = urlsplit(url)
    return urlunsplit(parts._replace(path="/postgres"))


# ---------------------------------------------------------------------------
# Session setup
# ---------------------------------------------------------------------------
@pytest.fixture(scope="session")
def test_database_url() -> Iterator[str]:
    """Create the test database if needed, then migrate it to head."""
    url = _test_database_url()
    if not url:
        pytest.skip("TEST_DATABASE_URL is not set and no DATABASE_URL is available")

    _create_database_if_missing(url)

    result = subprocess.run(
        # Note the argument order: alembic's global options (-x) must precede
        # the subcommand, otherwise it rejects them as unknown arguments.
        [sys.executable, "-m", "alembic", "-x", f"url={url}", "upgrade", "head"],
        cwd=BACKEND_DIR,
        capture_output=True,
        text=True,
        env={**os.environ, "PYTHONWARNINGS": "ignore"},
    )
    if result.returncode != 0:
        pytest.fail(
            "Failed to migrate the test database.\n"
            f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
        )
    yield url


def _create_database_if_missing(url: str) -> None:
    admin_url = _admin_database_url()
    if not admin_url:
        return
    db_name = urlsplit(url).path.lstrip("/")
    check = subprocess.run(
        [sys.executable, "-c", _EXISTS_SCRIPT, admin_url, db_name],
        capture_output=True,
        text=True,
        env={**os.environ, "PYTHONWARNINGS": "ignore"},
    )
    if check.returncode != 0:
        pytest.skip(
            "Cannot reach a PostgreSQL server for tests. Start it with "
            "`powershell -File scripts/local-services.ps1 start` or set TEST_DATABASE_URL.\n"
            f"{check.stderr.strip()}"
        )
    if check.stdout.strip() == "0":
        subprocess.run(
            [sys.executable, "-c", _CREATE_SCRIPT, admin_url, db_name],
            check=True,
            capture_output=True,
            text=True,
            env={**os.environ, "PYTHONWARNINGS": "ignore"},
        )


_EXISTS_SCRIPT = """
import asyncio, sys
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text

async def main():
    engine = create_async_engine(sys.argv[1])
    async with engine.connect() as conn:
        row = await conn.execute(
            text("SELECT count(*) FROM pg_database WHERE datname = :n"), {"n": sys.argv[2]}
        )
        print(row.scalar())
    await engine.dispose()

asyncio.run(main())
"""

_CREATE_SCRIPT = """
import asyncio, sys
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text

async def main():
    engine = create_async_engine(sys.argv[1], isolation_level="AUTOCOMMIT")
    async with engine.connect() as conn:
        # Identifier cannot be parameterised; the name is a test constant, not
        # user input, and is validated below.
        name = sys.argv[2]
        assert name.replace("_", "").isalnum(), "unsafe database name"
        await conn.execute(text(f'CREATE DATABASE "{name}"'))
    await engine.dispose()

asyncio.run(main())
"""


# ---------------------------------------------------------------------------
# Per-test database state
# ---------------------------------------------------------------------------
@pytest.fixture
async def db_engine(test_database_url: str):
    """Engine bound to the test database, disposed after the test."""
    engine = create_async_engine(test_database_url, poolclass=_NullPoolShim())
    try:
        yield engine
    finally:
        await engine.dispose()


def _NullPoolShim():  # noqa: N802 - factory, not a class
    from sqlalchemy.pool import NullPool

    return NullPool


@pytest.fixture
async def clean_tables(test_database_url: str):
    """Truncate every application table so each test starts from a known state.

    ``RESTART IDENTITY`` + ``CASCADE`` on the full table list is far faster and
    more reliable than trying to infer dependency order per test. It also
    leaves enum types and triggers intact, which are part of what we test.
    """
    engine = create_async_engine(test_database_url)
    tables = ", ".join(f'"{name}"' for name in Base.metadata.tables)
    try:
        async with engine.begin() as conn:
            await conn.exec_driver_sql(f"TRUNCATE {tables} RESTART IDENTITY CASCADE")
        yield
    finally:
        await engine.dispose()


@pytest.fixture
async def session(clean_tables, test_database_url: str) -> AsyncGenerator[AsyncSession, None]:
    """A clean, transactional session with no outer transaction wrapper.

    Deliberately not using the ``get_db`` dependency: several tests need to
    commit, and a savepoint-wrapped session would hide real transaction
    behaviour such as row locks and ``SELECT ... FOR UPDATE`` serialisation.
    """
    engine = create_async_engine(test_database_url)
    factory = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as sess:
        try:
            yield sess
        finally:
            if sess.in_transaction():
                await sess.rollback()
            await sess.close()
    await engine.dispose()


@pytest.fixture
def unique_suffix() -> str:
    """Short unique token for building collision-free slugs/SKUs in a test."""
    return uuid.uuid4().hex[:10]
