"""Application error contract.

Every failure the API returns to a client uses the same envelope, so the
frontend has exactly one error shape to render:

    {
      "error": {
        "code": "product_not_found",
        "message": "That product is no longer available.",
        "field_errors": { "email": ["Enter a valid email address."] },
        "request_id": "01J..."
      }
    }

Internal exception detail is logged server-side and never serialised into the
response. ``AppError`` subclasses carry a stable machine readable ``code`` that
the frontend can branch on, plus an HTTP status and an optional field level
validation map.
"""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.logging import get_logger

logger = get_logger(__name__)


class AppError(Exception):
    """Base class for every expected, client-facing failure."""

    status_code: int = status.HTTP_400_BAD_REQUEST
    code: str = "bad_request"
    message: str = "The request could not be completed."

    def __init__(
        self,
        message: str | None = None,
        *,
        code: str | None = None,
        status_code: int | None = None,
        field_errors: dict[str, list[str]] | None = None,
        extra: dict[str, Any] | None = None,
    ) -> None:
        self.message = message or self.message
        self.code = code or self.code
        self.status_code = status_code or self.status_code
        self.field_errors = field_errors or {}
        self.extra = extra or {}
        super().__init__(self.message)

    def to_payload(self, request_id: str | None = None) -> dict[str, Any]:
        body: dict[str, Any] = {
            "code": self.code,
            "message": self.message,
        }
        if self.field_errors:
            body["field_errors"] = self.field_errors
        if self.extra:
            body["details"] = self.extra
        if request_id:
            body["request_id"] = request_id
        return {"error": body}


# --------------------------------------------------------------------------
# 4xx
# --------------------------------------------------------------------------
class ValidationError(AppError):
    status_code = status.HTTP_422_UNPROCESSABLE_CONTENT
    code = "validation_error"
    message = "Some of the submitted values are not valid."


class NotFoundError(AppError):
    status_code = status.HTTP_404_NOT_FOUND
    code = "not_found"
    message = "We could not find what you were looking for."


class UnauthorizedError(AppError):
    status_code = status.HTTP_401_UNAUTHORIZED
    code = "unauthorized"
    message = "Please sign in to continue."


class ForbiddenError(AppError):
    status_code = status.HTTP_403_FORBIDDEN
    code = "forbidden"
    message = "You do not have permission to perform this action."


class ConflictError(AppError):
    status_code = status.HTTP_409_CONFLICT
    code = "conflict"
    message = "That action conflicts with the current state."


class InsufficientStockError(ConflictError):
    code = "insufficient_stock"
    message = "Some items are no longer available in the requested quantity."


class CouponError(ValidationError):
    code = "invalid_coupon"
    message = "That coupon code cannot be applied."


class RateLimitError(AppError):
    status_code = status.HTTP_429_TOO_MANY_REQUESTS
    code = "rate_limited"
    message = "Too many requests. Please slow down and try again shortly."


class PaymentError(AppError):
    status_code = status.HTTP_402_PAYMENT_REQUIRED
    code = "payment_failed"
    message = "The payment could not be completed."


# --------------------------------------------------------------------------
# 5xx
# --------------------------------------------------------------------------
class ServiceUnavailableError(AppError):
    status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    code = "service_unavailable"
    message = "We are temporarily unable to process this. Please try again."


class InternalError(AppError):
    status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
    code = "internal_error"
    message = "Something went wrong on our side. We have logged the details."


# --------------------------------------------------------------------------
# Success envelope (used by hand written endpoints that need it)
# --------------------------------------------------------------------------
def success_response(
    data: Any,
    *,
    request_id: str | None = None,
    meta: dict[str, Any] | None = None,
    status_code: int = status.HTTP_200_OK,
) -> JSONResponse:
    body: dict[str, Any] = {"data": data}
    if meta is not None:
        body["meta"] = meta
    if request_id:
        body["request_id"] = request_id
    return JSONResponse(status_code=status_code, content=body)


def _request_id(request: Request) -> str | None:
    return getattr(request.state, "request_id", None)


def _normalise_validation_details(exc: RequestValidationError) -> dict[str, list[str]]:
    """Convert pydantic errors into ``{field: [messages]}``.

    FastAPI/Pydantic report the *body* location for every error. For this API
    that is almost always the useful field name, so the last location segment
    is used, falling back to a generic key for non-field errors.
    """
    fields: dict[str, list[str]] = {}
    for error in exc.errors():
        location = [str(part) for part in error.get("loc", []) if part not in {"body", "query"}]
        key = location[-1] if location else "non_field_errors"
        message = str(error.get("msg", "Invalid value."))
        # Strip pydantic's "Value error, " prefix for cleaner copy.
        if message.startswith("Value error, "):
            message = message[len("Value error, ") :]
        fields.setdefault(key, []).append(message)
    return fields


def register_exception_handlers(app: FastAPI) -> None:
    """Install handlers so no unhandled exception can leak a stack trace."""

    @app.exception_handler(AppError)
    async def _app_error(request: Request, exc: AppError) -> JSONResponse:
        log = logger.bind(
            error_code=exc.code,
            status_code=exc.status_code,
            path=request.url.path,
            method=request.method,
        )
        if exc.status_code >= 500:
            log.error("request_failed", exc_info=exc)
        else:
            log.info("request_rejected", extra=exc.extra or None)
        return JSONResponse(
            status_code=exc.status_code,
            content=exc.to_payload(_request_id(request)),
        )

    @app.exception_handler(RequestValidationError)
    async def _validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
        logger.info(
            "request_validation_failed",
            path=request.url.path,
            method=request.method,
            fields=_normalise_validation_details(exc),
        )
        error = ValidationError(field_errors=_normalise_validation_details(exc))
        return JSONResponse(
            status_code=error.status_code,
            content=error.to_payload(_request_id(request)),
        )

    @app.exception_handler(StarletteHTTPException)
    async def _http_error(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        code_map = {
            400: "bad_request",
            401: "unauthorized",
            403: "forbidden",
            404: "not_found",
            405: "method_not_allowed",
            409: "conflict",
            429: "rate_limited",
        }
        detail = exc.detail if isinstance(exc.detail, str) else "Request failed."
        error = AppError(
            message=detail,
            code=code_map.get(exc.status_code, "http_error"),
            status_code=exc.status_code,
        )
        return JSONResponse(
            status_code=exc.status_code,
            content=error.to_payload(_request_id(request)),
            headers=getattr(exc, "headers", None),
        )

    @app.exception_handler(Exception)
    async def _unhandled(request: Request, exc: Exception) -> JSONResponse:
        # Log the real traceback with the request id, return an opaque message.
        logger.error(
            "unhandled_exception",
            path=request.url.path,
            method=request.method,
            exc_info=exc,
        )
        error = InternalError()
        return JSONResponse(
            status_code=error.status_code,
            content=error.to_payload(_request_id(request)),
        )
