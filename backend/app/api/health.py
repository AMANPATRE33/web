"""Liveness and readiness probes.

``GET /health`` is a shallow liveness check that never touches a dependency -
it exists so a platform health check can distinguish "process is alive" from
"process is wedged".

``GET /health/ready`` is the readiness check: it verifies the database and
Redis connectivity and reports each integration's configuration state. It
returns 503 when a hard dependency is down so that Railway stops routing
traffic, and 200 with ``status: "degraded"`` when an optional integration
(payment provider, email) is merely unconfigured.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Literal

from fastapi import APIRouter, Response, status
from pydantic import BaseModel, Field

from app import __version__
from app.core.config import get_settings
from app.core.logging import get_logger
from app.db.session import ping_database

logger = get_logger(__name__)

router = APIRouter(tags=["health"])

# Probes are called constantly by the platform; never rate limit them.
PROBE_PATHS = ("/health", "/health/live", "/health/ready")


class ComponentHealth(BaseModel):
    name: str
    status: Literal["ok", "degraded", "down", "skipped"]
    detail: str | None = None
    latency_ms: float | None = None


class HealthResponse(BaseModel):
    status: Literal["ok", "degraded", "down"]
    version: str = __version__
    environment: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    components: list[ComponentHealth] = Field(default_factory=list)


class LivenessResponse(BaseModel):
    status: Literal["ok"] = "ok"
    version: str = __version__


@router.get("/health", response_model=LivenessResponse, summary="Liveness probe")
async def liveness() -> LivenessResponse:
    return LivenessResponse()


@router.get("/health/live", response_model=LivenessResponse, include_in_schema=False)
async def liveness_alias() -> LivenessResponse:
    return LivenessResponse()


async def _check_redis() -> ComponentHealth:
    return await _probe_redis(
        name="redis",
        url=get_settings().redis_cache_url,
        # The readiness probe runs on the platform's health-check schedule.
        # It must answer in well under a second or the platform will kill an
        # otherwise healthy instance, so retries are disabled and the socket
        # timeout is short.
        attempts=0,
    )


async def _check_redis_job_queue() -> ComponentHealth:
    return await _probe_redis(
        name="redis_jobs",
        url=get_settings().redis_job_url,
        attempts=0,
    )


async def _probe_redis(*, name: str, url: str, attempts: int) -> ComponentHealth:
    import time

    from redis.asyncio import Redis
    from redis.backoff import NoBackoff
    from redis.retry import Retry

    started = time.perf_counter()
    try:
        client = Redis.from_url(
            url,
            socket_connect_timeout=1,
            socket_timeout=1,
            retry=Retry(NoBackoff(), attempts),
        )
        try:
            await client.ping()
        finally:
            await client.aclose()
    except Exception as exc:  # noqa: BLE001 - probes must never raise
        return ComponentHealth(
            name=name,
            status="degraded",
            detail=f"{type(exc).__name__}: {exc}",
            latency_ms=round((time.perf_counter() - started) * 1000, 2),
        )
    return ComponentHealth(
        name=name,
        status="ok",
        latency_ms=round((time.perf_counter() - started) * 1000, 2),
    )


@router.get(
    "/health/ready",
    response_model=HealthResponse,
    summary="Readiness probe with dependency checks",
)
async def readiness(response: Response) -> HealthResponse:
    settings = get_settings()
    components: list[ComponentHealth] = []

    # --- hard dependency: postgres ---
    db_ok = await ping_database(settings)
    components.append(
        ComponentHealth(
            name="postgres",
            status="ok" if db_ok else "down",
            detail=None if db_ok else "cannot connect to DATABASE_URL",
        )
    )

    # --- soft dependencies ---
    components.append(await _check_redis())
    components.append(await _check_redis_job_queue())

    components.append(
        ComponentHealth(
            name="supabase",
            status="ok" if settings.supabase_is_configured else "degraded",
            detail=None
            if settings.supabase_is_configured
            else "SUPABASE_SERVICE_ROLE_KEY not set - admin auth operations disabled",
        )
    )
    components.append(
        ComponentHealth(
            name="razorpay",
            status="ok" if settings.razorpay_is_configured else "degraded",
            detail=None
            if settings.razorpay_is_configured
            else f"razorpay credentials not set ({settings.razorpay_mode} mode)",
        )
    )
    components.append(
        ComponentHealth(
            name="email",
            status="ok" if settings.email_provider != "console" else "degraded",
            detail=f"provider={settings.email_provider}",
        )
    )

    if any(c.status == "down" for c in components):
        overall = "down"
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    elif any(c.status == "degraded" for c in components):
        overall = "degraded"
    else:
        overall = "ok"

    payload = HealthResponse(
        status=overall,  # type: ignore[arg-type]
        environment=settings.app_env,
        components=components,
    )
    if overall != "ok":
        logger.warning("readiness_degraded", components=[c.model_dump() for c in components])
    return payload


@router.get("/api/version", include_in_schema=False)
async def version() -> dict[str, Any]:
    settings = get_settings()
    return {
        "version": __version__,
        "environment": settings.app_env,
        "api_version": "v1",
    }
