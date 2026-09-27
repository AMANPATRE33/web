"""Supabase Auth admin operations, isolated behind one service class.

Business logic never touches the Supabase client directly. That keeps three
things in one place:

* the service role key, which is loaded from settings and never logged;
* the fact that the official client is synchronous, so every call is pushed to a
  worker thread rather than blocking the event loop;
* the translation of Supabase's exception hierarchy into this application's
  error contract, so a route does not need to know what a ``AuthApiError`` is.
"""

from __future__ import annotations

import asyncio
import uuid
from dataclasses import dataclass
from typing import Any

from supabase import (
    AuthApiError,  # re-exported by the SDK root
    Client,
    create_client,
)

from app.core.config import Settings, get_settings
from app.core.errors import AppError, ConflictError, NotFoundError, ValidationError
from app.core.logging import get_logger, scrub

logger = get_logger(__name__)


@dataclass(slots=True)
class ManagedUser:
    id: uuid.UUID
    email: str
    email_confirmed: bool
    phone: str | None
    user_metadata: dict[str, Any]
    created_at: str | None
    last_sign_in_at: str | None
    banned_until: str | None


class SupabaseAuthService:
    """Thin async wrapper over the Supabase Auth admin API."""

    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()
        self._client: Client | None = None

    def _require_configured(self) -> None:
        if not self._settings.supabase_is_configured:
            raise AppError(
                "Account management is unavailable because the backend is not "
                "configured for Supabase admin access.",
                code="auth_not_configured",
                status_code=503,
            )

    @property
    def client(self) -> Client:
        self._require_configured()
        if self._client is None:
            self._client = create_client(
                self._settings.supabase_url,
                self._settings.supabase_service_role_key.get_secret_value(),
                options={
                    "auth": {
                        "auto_refresh_token": False,
                        "persist_session": False,
                        "detect_session_in_url": False,
                    }
                },
            )
        return self._client

    async def _run(self, func: Any, *args: Any, **kwargs: Any) -> Any:
        """Execute a blocking Supabase call off the event loop."""
        return await asyncio.to_thread(func, *args, **kwargs)

    # ------------------------------------------------------------------
    # Reads
    # ------------------------------------------------------------------
    async def get_user(self, user_id: uuid.UUID | str) -> ManagedUser:
        def _call() -> Any:
            return self.client.auth.admin.get_user_by_id(str(user_id))

        response = await self._run(_call)
        return self._to_managed(response)

    async def list_users(
        self, *, page: int = 1, per_page: int = 50
    ) -> tuple[list[ManagedUser], int]:
        def _call() -> Any:
            return self.client.auth.admin.list_users(page=page, per_page=per_page)

        response = await self._run(_call)
        users = [self._to_managed(item) for item in getattr(response, "users", [])]
        total = int(getattr(response, "total", len(users)) or len(users))
        return users, total

    async def find_user_by_email(self, email: str) -> ManagedUser | None:
        """Look a user up by email. ``get_user_by_email`` raises when absent."""

        def _call() -> Any:
            return self.client.auth.admin.get_user_by_email(email.strip().lower())

        try:
            response = await self._run(_call)
        except AuthApiError as exc:
            if _is_not_found(exc):
                return None
            raise
        return self._to_managed(response)

    # ------------------------------------------------------------------
    # Writes
    # ------------------------------------------------------------------
    async def create_user(
        self,
        *,
        email: str,
        password: str,
        email_confirm: bool = True,
        user_metadata: dict[str, Any] | None = None,
    ) -> ManagedUser:
        def _call() -> Any:
            return self.client.auth.admin.create_user(
                {
                    "email": email.strip().lower(),
                    "password": password,
                    "email_confirm": email_confirm,
                    "user_metadata": user_metadata or {},
                }
            )

        response = await self._run(_call)
        logger.info("supabase_user_created", email=email.strip().lower())
        return self._to_managed(response)

    async def update_user(
        self, user_id: uuid.UUID | str, attributes: dict[str, Any]
    ) -> ManagedUser:
        def _call() -> Any:
            return self.client.auth.admin.update_user_by_id(str(user_id), attributes)

        try:
            response = await self._run(_call)
        except AuthApiError as exc:
            raise _translate(exc) from exc
        logger.info("supabase_user_updated", user_id=str(user_id), fields=sorted(attributes))
        return self._to_managed(response)

    async def delete_user(
        self, user_id: uuid.UUID | str, *, should_soft_delete: bool = False
    ) -> None:
        def _call() -> Any:
            return self.client.auth.admin.delete_user(
                str(user_id), should_soft_delete=should_soft_delete
            )

        try:
            await self._run(_call)
        except AuthApiError as exc:
            raise _translate(exc) from exc
        logger.info("supabase_user_deleted", user_id=str(user_id), soft=should_soft_delete)

    async def ban_user(self, user_id: uuid.UUID | str, *, until: str | None = None) -> ManagedUser:
        def _call() -> Any:
            return self.client.auth.admin.update_user_by_id(
                str(user_id), {"ban_duration": until or "876000h"}
            )

        try:
            response = await self._run(_call)
        except AuthApiError as exc:
            raise _translate(exc) from exc
        return self._to_managed(response)

    async def unban_user(self, user_id: uuid.UUID | str) -> ManagedUser:
        def _call() -> Any:
            return self.client.auth.admin.update_user_by_id(str(user_id), {"ban_duration": "none"})

        try:
            response = await self._run(_call)
        except AuthApiError as exc:
            raise _translate(exc) from exc
        return self._to_managed(response)

    async def send_password_reset(self, email: str, *, redirect_to: str | None = None) -> None:
        """Ask Supabase to email a recovery link.

        Always reports success to the caller regardless of whether the address
        exists: a different response for a known and an unknown address is an
        account-enumeration oracle.
        """
        target = (
            redirect_to or self._settings.redirect_url_list[0]
            if (self._settings.redirect_url_list)
            else None
        )

        def _call() -> Any:
            return self.client.auth.reset_password_for_email(
                email.strip().lower(),
                {"redirect_to": target} if target else None,
            )

        try:
            await self._run(_call)
        except AuthApiError as exc:
            # Deliberately swallowed: the response must not depend on whether
            # the account exists. Logged for support, never surfaced.
            logger.warning("password_reset_request_failed", error=scrub(str(exc)))
            return
        logger.info("password_reset_requested", email=email.strip().lower())

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------
    @staticmethod
    def _to_managed(response: Any) -> ManagedUser:
        user = getattr(response, "user", response)
        return ManagedUser(
            id=uuid.UUID(str(user.id)),
            email=str(user.email or ""),
            email_confirmed=bool(
                getattr(user, "email_confirmed_at", None) or getattr(user, "confirmed_at", None)
            ),
            phone=getattr(user, "phone", None),
            user_metadata=dict(getattr(user, "user_metadata", None) or {}),
            created_at=str(getattr(user, "created_at", "") or "") or None,
            last_sign_in_at=str(getattr(user, "last_sign_in_at", "") or "") or None,
            banned_until=str(getattr(user, "banned_until", "") or "") or None,
        )


def _is_not_found(exc: AuthApiError) -> bool:
    status = getattr(exc, "status", None)
    if status in (404, "404"):
        return True
    message = str(exc).lower()
    return "not found" in message or "does not exist" in message


def _translate(exc: AuthApiError) -> AppError:
    """Map a Supabase auth error onto this application's error contract."""
    status = getattr(exc, "status", None)
    message = str(exc)
    lowered = message.lower()

    if _is_not_found(exc):
        return NotFoundError("That account could not be found.", code="user_not_found")
    if status in (422, "422") or ("already" in lowered and "registered" in lowered):
        return ConflictError(
            "An account with that email already exists.",
            code="email_already_registered",
        )
    if "password" in lowered and ("weak" in lowered or "invalid" in lowered):
        return ValidationError(
            "Choose a stronger password.",
            code="weak_password",
        )
    if status in (429, "429"):
        return AppError(
            "Too many attempts. Please wait a moment and try again.",
            code="auth_rate_limited",
            status_code=429,
        )
    logger.error("supabase_auth_error", status=status, error=scrub(message))
    return AppError(
        "We could not complete that account request. Please try again.",
        code="auth_provider_error",
        status_code=502,
    )


_service: SupabaseAuthService | None = None


def get_auth_service() -> SupabaseAuthService:
    """Shared service instance."""
    global _service
    if _service is None:
        _service = SupabaseAuthService()
    return _service


def reset_auth_service() -> None:
    global _service
    _service = None
