"""ASGI middleware: request ids, access logging, security headers, CORS.

The CORS configuration deliberately refuses to fall back to a wildcard origin.
In production an unlisted origin is a configuration error, not something to be
papered over with ``allow_origins=["*"]``.
"""

from __future__ import annotations

import time
import uuid

import structlog
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.middleware.cors import CORSMiddleware
from starlette.types import ASGIApp

from app.core.config import Settings
from app.core.logging import get_logger

logger = get_logger(__name__)

REQUEST_ID_HEADER = "X-Request-ID"
# Endpoints that must never be rate limited or logged with a body.
_NOISY_PATHS = {"/health", "/api/health", "/metrics"}


class RequestContextMiddleware(BaseHTTPMiddleware):
    """Assign a request id, bind it to the log context, time the request."""

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        incoming = request.headers.get(REQUEST_ID_HEADER)
        request_id = incoming or f"req_{uuid.uuid4().hex[:20]}"
        request.state.request_id = request_id

        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(request_id=request_id)

        started = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception:
            duration_ms = round((time.perf_counter() - started) * 1000, 2)
            logger.exception(
                "request_failed",
                method=request.method,
                path=request.url.path,
                duration_ms=duration_ms,
            )
            raise
        duration_ms = round((time.perf_counter() - started) * 1000, 2)
        response.headers[REQUEST_ID_HEADER] = request_id
        response.headers["X-Response-Time-ms"] = str(duration_ms)

        if request.url.path not in _NOISY_PATHS:
            log = logger.bind(
                method=request.method,
                path=request.url.path,
                status_code=response.status_code,
                duration_ms=duration_ms,
            )
            if response.status_code >= 500:
                log.error("request_completed")
            elif response.status_code >= 400:
                log.warning("request_completed")
            else:
                log.info("request_completed")

        return response


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Conservative security headers for an API surface."""

    def __init__(self, app: ASGIApp, *, enabled: bool = True) -> None:
        super().__init__(app)
        self.enabled = enabled

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        response = await call_next(request)
        if not self.enabled:
            return response

        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        response.headers.setdefault("X-DNS-Prefetch-Control", "off")
        response.headers.setdefault(
            "Permissions-Policy", "camera=(), microphone=(), geolocation=(), interest-cohort=()"
        )
        # This API serves JSON only. A restrictive CSP stops any successful
        # HTML/script injection attempt from executing.
        response.headers.setdefault(
            "Content-Security-Policy",
            "default-src 'none'; frame-ancestors 'none'; base-uri 'none'",
        )
        if request.url.scheme == "https" or request.headers.get("x-forwarded-proto") == "https":
            response.headers.setdefault(
                "Strict-Transport-Security", "max-age=31536000; includeSubDomains"
            )
        return response


def register_middleware(app: ASGIApp, settings: Settings) -> None:  # type: ignore[type-arg]
    """Attach middleware in the correct outermost-to-innermost order."""
    # Outermost: request context must wrap CORS so CORS errors are logged too.
    app.add_middleware(
        SecurityHeadersMiddleware,
        enabled=settings.security_headers_enabled,  # type: ignore[call-arg]
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", REQUEST_ID_HEADER, "Idempotency-Key"],
        expose_headers=[REQUEST_ID_HEADER, "X-Response-Time-ms"],
        max_age=600,
    )
    app.add_middleware(RequestContextMiddleware)
