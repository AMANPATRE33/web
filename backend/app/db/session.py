"""Async engine, session factory and request scoped session dependency."""

from __future__ import annotations

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from sqlalchemy import event, text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import NullPool

from app.core.config import Settings, get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)


def _engine_kwargs(settings: Settings, url: str) -> dict[str, object]:
    is_sqlite = url.startswith("sqlite")
    kwargs: dict[str, object] = {
        "echo": settings.db_echo,
        "pool_pre_ping": True,
        "future": True,
    }
    if is_sqlite:
        # Only used by the offline unit-test harness; the product runs on Postgres.
        kwargs["poolclass"] = NullPool
    else:
        kwargs.update(
            pool_size=settings.db_pool_size,
            max_overflow=settings.db_max_overflow,
            pool_timeout=settings.db_pool_timeout,
            pool_recycle=settings.db_pool_recycle,
        )
    return kwargs


_engine: AsyncEngine | None = None
_read_engine: AsyncEngine | None = None
_sessionmaker: async_sessionmaker[AsyncSession] | None = None


def _apply_connect_hooks(engine: AsyncEngine, settings: Settings) -> None:
    if engine.url.get_backend_name() == "sqlite":
        return

    @event.listens_for(engine.sync_engine, "connect")
    def _set_session_defaults(dbapi_connection: object, _record: object) -> None:
        cursor = dbapi_connection.cursor()  # type: ignore[attr-defined]
        try:
            # Cap runaway queries at the database, not just in the app.
            cursor.execute(
                f"SET statement_timeout = {int(settings.db_statement_timeout_ms)}"
            )
            # Deterministic server-side UTC timestamps.
            cursor.execute("SET TIME ZONE 'UTC'")
        finally:
            cursor.close()

    @event.listens_for(engine.sync_engine, "connect")
    def _register_types(dbapi_connection: object, _record: object) -> None:
        # pgcrypto is installed by the bootstrap/migration; ensure the search
        # path resolves gen_random_uuid() on every Supabase plan size.
        with dbapi_connection.cursor() as cursor:  # type: ignore[attr-defined]
            cursor.execute("SET search_path = public, extensions")


def get_engine(settings: Settings | None = None, *, read_only: bool = False) -> AsyncEngine:
    """Return (and lazily build) the async engine."""
    global _engine, _read_engine, _sessionmaker

    settings = settings or get_settings()
    if read_only:
        if _read_engine is None:
            _read_engine = create_async_engine(
                settings.effective_read_database_url,
                **_engine_kwargs(settings, settings.effective_read_database_url),
            )
            _apply_connect_hooks(_read_engine, settings)
            logger.info("read_engine_created")
        return _read_engine

    if _engine is None:
        _engine = create_async_engine(
            settings.effective_database_url,
            **_engine_kwargs(settings, settings.effective_database_url),
        )
        _apply_connect_hooks(_engine, settings)
        _sessionmaker = async_sessionmaker(
            bind=_engine,
            class_=AsyncSession,
            expire_on_commit=False,
            autoflush=False,
        )
        logger.info("engine_created", dialect=_engine.dialect.name)
    return _engine


def get_sessionmaker() -> async_sessionmaker[AsyncSession]:
    if _sessionmaker is None:
        get_engine()
    assert _sessionmaker is not None  # noqa: S101 - invariant, not user input
    return _sessionmaker


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency: one transaction-scoped session per request.

    The session is rolled back on error and closed on exit. Commit is the
    caller's explicit responsibility inside service functions, which keeps
    transaction boundaries visible in the code that needs them.
    """
    async with get_sessionmaker()() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


@asynccontextmanager
async def session_scope() -> AsyncGenerator[AsyncSession, None]:
    """Transactional scope for scripts, workers and tests.

    Commits on clean exit, rolls back on error.
    """
    async with get_sessionmaker()() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def ping_database(settings: Settings | None = None) -> bool:
    """Connectivity probe used by the health endpoint."""
    try:
        engine = get_engine(settings)
        async with engine.connect() as connection:
            await connection.execute(text("SELECT 1"))
        return True
    except Exception as exc:  # noqa: BLE001 - health probe must never raise
        logger.warning("database_ping_failed", error=str(exc))
        return False


async def dispose_engine() -> None:
    """Close pooled connections. Called on application shutdown."""
    global _engine, _read_engine, _sessionmaker
    for engine in (_engine, _read_engine):
        if engine is not None:
            await engine.dispose()
    _engine = _read_engine = _sessionmaker = None
    logger.info("engine_disposed")
