"""FastAPI application factory and ASGI entrypoint.

Run locally:      uvicorn app.main:app --reload
Railway start:    uvicorn app.main:app --host 0.0.0.0 --port $PORT
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from collections.abc import AsyncIterator

from fastapi import FastAPI
from fastapi.responses import ORJSONResponse

from app import __version__
from app.api.health import router as health_router
from app.api.v1.router import router as v1_router
from app.core.config import get_settings
from app.core.errors import register_exception_handlers
from app.core.logging import configure_logging, get_logger
from app.core.middleware import register_middleware
from app.db.session import dispose_engine

settings = get_settings()
configure_logging(settings)
logger = get_logger(__name__)

DESCRIPTION = """
Production REST API for the storefront platform.

**Guarantees**

* Every price, discount, shipping charge, tax and stock figure is recomputed on
  the server. Values supplied by a client are treated as untrusted hints.
* Roles are resolved from the verified Supabase JWT and the ``profiles`` table.
  A role sent by the browser is never trusted.
* Errors use a single envelope: `{"error": {"code", "message", "request_id"}}`.
* All monetary amounts are integer minor units (paise).
"""

TAGS_METADATA: list[dict[str, object]] = [
    {"name": "health", "description": "Liveness and readiness probes."},
    {"name": "catalog", "description": "Public product and category browsing."},
    {"name": "search", "description": "Product search and suggestions."},
    {"name": "cart", "description": "Server authoritative shopping cart."},
    {"name": "wishlist", "description": "Saved products, persisted per customer."},
    {"name": "checkout", "description": "Address, shipping and order draft creation."},
    {"name": "payments", "description": "Razorpay order creation, verification, webhooks."},
    {"name": "orders", "description": "Customer order history and order detail."},
    {"name": "account", "description": "Profile, addresses and notifications."},
    {"name": "reviews", "description": "Product reviews and ratings."},
    {"name": "admin", "description": "Staff only operations. Server enforced role checks."},
]


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    logger.info(
        "startup",
        env=settings.app_env,
        version=__version__,
        docs=settings.api_docs_url,
    )
    if settings.is_production:
        logger.info(
            "production_boot_checks",
            razorpay=bool(settings.razorpay_is_configured),
            supabase=bool(settings.supabase_is_configured),
            email_provider=settings.email_provider,
        )
    try:
        yield
    finally:
        await dispose_engine()
        logger.info("shutdown_complete")


def create_app() -> FastAPI:
    app = FastAPI(
        title="Storefront API",
        description=DESCRIPTION,
        version=__version__,
        default_response_class=ORJSONResponse,
        openapi_tags=TAGS_METADATA,
        openapi_url="/api/openapi.json",
        docs_url=settings.api_docs_url,
        redoc_url=settings.api_redoc_url,
        lifespan=lifespan,
        # Trust X-Forwarded-* from the platform proxy (Vercel -> Railway).
        forwarded_allow_ips="*",
    )

    register_middleware(app, settings)
    register_exception_handlers(app)

    app.include_router(health_router)
    app.include_router(v1_router, prefix="/api/v1", tags=["v1"])

    @app.get("/", include_in_schema=False)
    async def root() -> dict[str, str]:
        return {
            "service": settings.app_name,
            "version": __version__,
            "api": "/api/v1",
            "health": "/health",
            "docs": settings.api_docs_url or "disabled in production",
        }

    return app


app = create_app()
