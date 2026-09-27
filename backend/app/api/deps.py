"""FastAPI dependencies for authentication, authorisation and CSRF.

## How a request is authenticated

Two mechanisms are accepted, in priority order:

1. ``Authorization: Bearer <access_token>`` - used by the Next.js **server
   components** (which have no browser cookies) and by any non-browser client.
2. The Supabase session cookie - used by the browser, where the session lives
   in an httpOnly cookie and never in ``localStorage``.

Cookie authentication is why CSRF protection exists. A bearer token is not sent
automatically by the browser, so a cross-site page cannot forge it; a cookie is,
so a cross-site form POST would carry a valid session without the attacker's
site ever reading the token. ``require_csrf`` therefore enforces a
double-submit check on every state-changing request that authenticated via
cookie.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.errors import ForbiddenError, UnauthorizedError
from app.core.logging import get_logger
from app.core.security import SupabasePrincipal, SupabaseTokenVerifier
from app.db.session import get_db
from app.models.enums import UserRole
from app.models.identity import Profile

logger = get_logger(__name__)

#: Cookie written by @supabase/ssr. Both spellings are checked because the
#: cookie name is configurable and differs between SSR and client helpers.
SESSION_COOKIE_NAMES = (
    "sb-access-token",
    "sb-auth-token",
    "supabase-auth-token",
)

CSRF_HEADER_NAME = "X-CSRF-Token"
CSRF_COOKIE_NAME = "csrf_token"
CSRF_PROTECTED_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})

_token_verifier: SupabaseTokenVerifier | None = None


def get_token_verifier() -> SupabaseTokenVerifier:
    """Process-wide verifier, so the JWKS cache is shared across requests."""
    global _token_verifier
    if _token_verifier is None:
        _token_verifier = SupabaseTokenVerifier(get_settings())
    return _token_verifier


async def reset_token_verifier() -> None:
    """Close and drop the verifier. Used on shutdown and between tests."""
    global _token_verifier
    if _token_verifier is not None:
        await _token_verifier.aclose()
    _token_verifier = None


@dataclass(slots=True)
class CurrentUser:
    """The authenticated caller, with the role resolved from the database."""

    principal: SupabasePrincipal
    profile: Profile
    via_cookie: bool

    @property
    def id(self) -> uuid.UUID:
        return self.profile.id

    @property
    def email(self) -> str:
        return self.profile.email

    @property
    def role(self) -> UserRole:
        return self.profile.role

    @property
    def is_admin(self) -> bool:
        return self.profile.role == UserRole.ADMIN


def _extract_token(request: Request) -> tuple[str | None, bool]:
    """Return ``(token, via_cookie)`` from the request, or ``(None, False)``."""
    header = request.headers.get("authorization")
    if header and header.lower().startswith("bearer "):
        token = header[7:].strip()
        if token:
            return token, False

    for cookie_name in SESSION_COOKIE_NAMES:
        value = request.cookies.get(cookie_name)
        if not value:
            continue
        # @supabase/ssr may store either the raw JWT or a base64url JSON chunk
        # prefixed with "base64-".
        if value.startswith("base64-"):
            import base64
            import json as _json

            try:
                decoded = base64.urlsafe_b64decode(value[7:] + "=" * (-len(value[7:]) % 4))
                payload = _json.loads(decoded)
                token = payload.get("access_token") if isinstance(payload, dict) else None
            except (ValueError, UnicodeDecodeError):
                continue
            if token:
                return str(token), True
            continue
        return value, True

    return None, False


async def ensure_profile(
    session: AsyncSession,
    principal: SupabasePrincipal,
    *,
    full_name: str | None = None,
) -> Profile:
    """Load the caller's profile, creating it if the trigger has not yet run.

    The Supabase trigger (``database/sql/004_auth_integration.sql``) creates the
    row on signup. This is the second, independent path: a profile must exist
    before any customer-scoped table can reference it, and a user created
    through the dashboard or a future code path might not have triggered it.
    """
    result = await session.execute(select(Profile).where(Profile.id == principal.user_id))
    profile = result.scalar_one_or_none()

    if profile is None:
        # Only a non-empty email is stored; auth.users always has one, but a
        # claim could in principle be absent.
        email = (principal.email or "").strip().lower()
        if not email:
            raise UnauthorizedError("Your account is missing an email address.")
        profile = Profile(
            id=principal.user_id,
            email=email,
            full_name=full_name,
            # Never trust a role from the token or from sign-up metadata.
            role=UserRole.CUSTOMER,
        )
        session.add(profile)
        await session.flush()
        logger.info("profile_created_on_demand", profile_id=str(profile.id))
        return profile

    if not profile.is_active:
        raise ForbiddenError(
            "This account has been deactivated. Please contact support.",
            code="account_deactivated",
        )
    return profile


async def get_optional_user(
    request: Request,
    session: Annotated[AsyncSession, Depends(get_db)],
    verifier: Annotated[SupabaseTokenVerifier, Depends(get_token_verifier)],
) -> CurrentUser | None:
    """Resolve the caller if a valid token is present, otherwise ``None``.

    Used by endpoints that behave differently for signed-in visitors (a
    wishlist count in the cart, for example) but must never fail for anonymous
    traffic.
    """
    token, via_cookie = _extract_token(request)
    if not token:
        return None
    try:
        principal = await verifier.verify(token)
    except UnauthorizedError:
        return None
    profile = await ensure_profile(session, principal)
    return CurrentUser(principal=principal, profile=profile, via_cookie=via_cookie)


async def get_current_user(
    user: Annotated[CurrentUser | None, Depends(get_optional_user)],
) -> CurrentUser:
    """Require authentication."""
    if user is None:
        raise UnauthorizedError()
    return user


async def require_csrf(
    request: Request,
    user: Annotated[CurrentUser, Depends(get_current_user)],
) -> CurrentUser:
    """Double-submit CSRF check for cookie-authenticated writes.

    A bearer-token request is exempt: the browser does not attach
    ``Authorization`` on its own, so a cross-site request cannot supply a valid
    one. A cookie-authenticated write must echo a token that is readable by
    JavaScript, which a cross-origin page cannot do.
    """
    if not user.via_cookie:
        return user
    if request.method.upper() not in CSRF_PROTECTED_METHODS:
        return user

    from app.core.security import constant_time_equals

    header_value = request.headers.get(CSRF_HEADER_NAME, "")
    cookie_value = request.cookies.get(CSRF_COOKIE_NAME, "")
    if not header_value or not cookie_value:
        raise ForbiddenError(
            "This request is missing its security token. Please refresh and try again.",
            code="csrf_token_missing",
        )
    if not constant_time_equals(header_value, cookie_value):
        logger.warning(
            "csrf_check_failed",
            path=request.url.path,
            method=request.method,
        )
        raise ForbiddenError(
            "Your session could not be verified. Please refresh and try again.",
            code="csrf_token_invalid",
        )
    return user


async def get_current_admin(
    user: Annotated[CurrentUser, Depends(require_csrf)],
) -> CurrentUser:
    """Require the ADMIN role, re-read from the database.

    The role in the JWT is never consulted. A token minted while the account
    was a customer stays a customer token, and revoking admin takes effect on
    the next request rather than whenever the token happens to expire.
    """
    if user.role != UserRole.ADMIN:
        logger.warning(
            "admin_access_denied",
            profile_id=str(user.id),
            role=str(user.role),
        )
        raise ForbiddenError(
            "You do not have permission to perform this action.",
            code="admin_required",
        )
    return user


async def require_safe_write(request: Request) -> None:
    """Guard a state-changing request that may come from an anonymous visitor.

    ## Why this exists separately from ``require_csrf``

    The double-submit check needs a CSRF cookie, and an anonymous visitor has
    none - so ``require_csrf`` (which chains off ``get_current_user``) rejects
    every guest write, and a guest cart becomes read-only. That is a real bug,
    not a theoretical one: a shopper who has not signed in must be able to build
    a basket.

    The threat is also smaller here. Forcing a cross-origin page to mutate an
    anonymous cart achieves nothing an attacker wants: the cart belongs to
    whoever holds the cookie, the worst outcome is a stranger's basket gaining
    an item, and no money or data moves.

    So anonymous writes are guarded by **origin**, which is the correct control
    for a request with no ambient authority:

    * ``Sec-Fetch-Site: cross-site`` is rejected outright. Every current browser
      sends it and it cannot be forged by page script, because it is set by the
      browser, not by ``fetch``.
    * An ``Origin`` that is not in the allowlist is rejected.
    * A write with *neither* header is allowed, because a same-origin
      non-browser client (curl, a server-to-server call) sends neither and
      refusing it would break legitimate integrations without adding safety -
      such a client is not a browser, so it is not subject to CSRF.

    Authenticated writes still go through the full double-submit check, which is
    the stronger control and is unchanged.
    """
    if request.method.upper() not in CSRF_PROTECTED_METHODS:
        return

    fetch_site = request.headers.get("sec-fetch-site", "").strip().lower()
    if fetch_site == "cross-site":
        logger.warning(
            "cross_site_write_blocked",
            path=request.url.path,
            method=request.method,
        )
        raise ForbiddenError(
            "This request came from another site and was blocked.",
            code="cross_site_write_blocked",
        )

    origin = request.headers.get("origin")
    if not origin:
        # Not a browser form/fetch. No ambient authority to abuse.
        return

    settings = get_settings()
    allowed = set(settings.cors_origin_list)
    if origin not in allowed:
        logger.warning(
            "bad_origin_write_blocked",
            origin=origin,
            path=request.url.path,
        )
        raise ForbiddenError(
            "This request came from an unrecognised origin and was blocked.",
            code="bad_origin",
        )


#: For writes that a signed-out visitor must be able to perform, i.e. the cart.
SafeWrite = Annotated[None, Depends(require_safe_write)]


# Convenient aliases for route signatures.
OptionalUser = Annotated[CurrentUser | None, Depends(get_optional_user)]
AuthUser = Annotated[CurrentUser, Depends(get_current_user)]
AdminUser = Annotated[CurrentUser, Depends(get_current_admin)]


def settings_dependency() -> Settings:
    return get_settings()
