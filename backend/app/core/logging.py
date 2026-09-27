"""Structured logging.

Emits newline delimited JSON in deployed environments so Railway/Datadog ingest
can parse it, and a human readable console renderer during local development.
Every log line carries the request id, which is also returned to the caller in
the ``X-Request-ID`` response header, so a customer-reported failure can be
traced to exact server logs.
"""

from __future__ import annotations

import logging
import sys
from typing import Any

import structlog

from app.core.config import Settings

# Attributes structlog adds to every event. Stripped from the console renderer
# so local output stays readable.
_LOGGER_CONTEXT = [
    "request_id",
    "user_id",
    "method",
    "path",
    "status_code",
    "duration_ms",
]


def configure_logging(settings: Settings) -> None:
    """Install structlog processors and stdlib logging configuration."""
    json_output = not settings.is_development

    shared_processors: list[Any] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.UnicodeDecoder(),
    ]

    if json_output:
        shared_processors.append(structlog.processors.format_exc_info)
        shared_processors.append(
            structlog.processors.EventRenamer("message", replace_by="_event")
        )

    renderer: Any
    if json_output:
        renderer = structlog.processors.JSONRenderer(sort_keys=True)
    else:
        renderer = structlog.dev.ConsoleRenderer(
            colors=sys.stdout.isatty(),
            exception_formatter=structlog.dev.plain_traceback,
        )

    structlog.configure(
        processors=[*shared_processors, structlog.stdlib.ProcessorFormatter.wrap_for_formatter],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    formatter = structlog.stdlib.ProcessorFormatter(
        foreign_pre_chain=shared_processors,
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            renderer,
        ],
    )

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)

    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(settings.log_level)

    # Uvicorn installs its own handlers; route them through structlog instead.
    for name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        uvicorn_logger = logging.getLogger(name)
        uvicorn_logger.handlers.clear()
        uvicorn_logger.propagate = True

    # SQLAlchemy is extremely chatty at INFO.
    logging.getLogger("sqlalchemy.engine").setLevel(
        logging.INFO if settings.db_echo else logging.WARNING
    )
    # Alembic/Alembic runtime noise
    logging.getLogger("alembic").setLevel(logging.WARNING)


def get_logger(name: str | None = None, **initial_values: Any) -> Any:
    """Return a bound structlog logger."""
    return structlog.get_logger(name, **initial_values)


def scrub(value: Any, *, keys: tuple[str, ...] = ()) -> Any:
    """Recursively remove sensitive values before they reach a log sink."""
    sensitive = {"password", "secret", "token", "authorization", "cookie", "key", *keys}

    if isinstance(value, dict):
        return {
            k: ("***" if any(s in k.lower() for s in sensitive) else scrub(v, keys=keys))
            for k, v in value.items()
        }
    if isinstance(value, list | tuple):
        return [scrub(v, keys=keys) for v in value]
    return value
