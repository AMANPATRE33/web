"""Cryptographic verification. Nothing here trusts an unverified input.

Three independent verification schemes live in this module:

* **Supabase access tokens** - HS256 with the project JWT secret (legacy
  projects) or ES256/RS256 via the project's JWKS endpoint (new projects, and
  the Supabase default going forward). The role claim in the token is treated as
  a hint; the authoritative role is re-read from ``profiles``.
* **Razorpay payment signatures** - HMAC-SHA256 over ``order_id|payment_id``.
* **Razorpay webhook signatures** - HMAC-SHA256 over the **raw request body**.
  A parsed-and-reserialised body will not reproduce the same digest, so the raw
  bytes are required and the webhook route is careful to preserve them.

Every comparison uses ``hmac.compare_digest``. A timing-variable string
comparison is a real, if slow, attack against a signature check.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
import uuid
from dataclasses import dataclass, field
from typing import Any

import httpx
import jwt
from jwt import InvalidTokenError, PyJWK, PyJWKSet

from app.core.config import Settings
from app.core.errors import UnauthorizedError
from app.core.logging import get_logger

logger = get_logger(__name__)

#: Supabase tokens are refreshed often; cache JWKS briefly to avoid a network
#: round trip per request, but long enough to survive a key rotation.
JWKS_CACHE_SECONDS = 3600
JWKS_REFRESH_MARGIN_SECONDS = 300


def _b64url_decode(segment: str) -> bytes:
    padding = "=" * (-len(segment) % 4)
    return base64.urlsafe_b64decode(segment + padding)


@dataclass(slots=True)
class SupabasePrincipal:
    """A verified Supabase user, as far as this API is concerned."""

    user_id: uuid.UUID
    email: str | None
    claims: dict[str, Any] = field(default_factory=dict)
    #: True when the request authenticated with a cookie rather than a bearer
    #: token, which is what makes CSRF protection mandatory.
    via_cookie: bool = False

    @property
    def token_role(self) -> str | None:
        """The role claim as asserted by the token.

        Informational only. ``require_admin`` compares against the value read
        from the ``profiles`` table, never against this.
        """
        metadata = self.claims.get("user_metadata") or {}
        role = metadata.get("role")
        if isinstance(role, str):
            return role
        app_metadata = self.claims.get("app_metadata") or {}
        roles = app_metadata.get("roles")
        if isinstance(roles, list) and roles:
            return str(roles[0])
        return None


class SupabaseTokenVerifier:
    """Validates Supabase access tokens.

    Both key strategies are supported because Supabase projects exist in both
    states and a store cannot know which one it will be given:

    * ``SUPABASE_JWT_SECRET`` set  -> HS256, verified with the shared secret.
    * ``SUPABASE_JWT_SECRET`` unset -> ES256/RS256, verified against the JWKS
      document served by the project itself, cached in-process.
    """

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._jwks: PyJWKSet | None = None
        self._jwks_fetched_at: float = 0.0
        self._http: httpx.AsyncClient | None = None

    async def _client(self) -> httpx.AsyncClient:
        if self._http is None or self._http.is_closed:
            self._http = httpx.AsyncClient(
                base_url=self._settings.supabase_url,
                timeout=httpx.Timeout(5.0, connect=2.0),
            )
        return self._http

    async def aclose(self) -> None:
        if self._http is not None and not self._http.is_closed:
            await self._http.aclose()
        self._http = None

    async def _jwks_set(self, force: bool = False) -> PyJWKSet:
        now = time.monotonic()
        fresh_enough = self._jwks is not None and (now - self._jwks_fetched_at) < (
            JWKS_CACHE_SECONDS - JWKS_REFRESH_MARGIN_SECONDS
        )
        if fresh_enough and not force:
            assert self._jwks is not None
            return self._jwks

        url = f"{self._settings.supabase_url.rstrip('/')}/auth/v1/.well-known/jwks.json"
        try:
            client = await self._client()
            response = await client.get(
                url, headers={"apikey": self._settings.supabase_publishable_key.get_secret_value()}
            )
            response.raise_for_status()
            data = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            if self._jwks is not None:
                # A transient failure must not log everyone out; keep serving the
                # cached keys until they actually expire.
                logger.warning("jwks_refresh_failed_using_cache", error=str(exc))
                return self._jwks
            logger.error("jwks_fetch_failed", error=str(exc))
            raise UnauthorizedError(
                "We could not verify your session. Please sign in again.",
                code="auth_unavailable",
                status_code=503,
            ) from exc

        self._jwks = PyJWKSet.from_dict(data)
        self._jwks_fetched_at = now
        logger.info("jwks_cached", keys=len(self._jwks.keys))
        return self._jwks

    def _decode_unverified(self, token: str) -> dict[str, Any]:
        """Peek at the header to choose a verification strategy.

        Nothing is trusted from this - it only selects *how* to verify.
        """
        try:
            header_segment = token.split(".")[0]
            header = json.loads(_b64url_decode(header_segment))
        except (IndexError, ValueError, UnicodeDecodeError) as exc:
            raise UnauthorizedError("Malformed authentication token.") from exc
        if not isinstance(header, dict):
            raise UnauthorizedError("Malformed authentication token.")
        return header

    async def verify(self, token: str) -> SupabasePrincipal:
        if not token or token.count(".") < 2:
            raise UnauthorizedError("Malformed authentication token.")

        header = self._decode_unverified(token)
        algorithm = str(header.get("alg", ""))

        secret = self._settings.supabase_jwt_secret
        if secret and secret.get_secret_value():
            if algorithm not in {"HS256", "HS384", "HS512"}:
                raise UnauthorizedError("Unexpected token signing algorithm.")
            return self._verify_hs256(token, secret.get_secret_value())

        if algorithm in {"ES256", "RS256", "RS384", "RS512"}:
            return await self._verify_asymmetric(token, header)

        raise UnauthorizedError(
            "Cannot verify this token.",
            code="auth_not_configured",
            status_code=503,
        )

    def _verify_hs256(self, token: str, secret: str) -> SupabasePrincipal:
        try:
            claims = jwt.decode(
                token,
                secret,
                algorithms=["HS256", "HS384", "HS512"],
                audience="authenticated",
                options={
                    "require": ["exp", "sub"],
                    "verify_aud": True,
                },
            )
        except InvalidTokenError as exc:
            raise UnauthorizedError("Your session has expired. Please sign in again.") from exc
        return self._principal(claims)

    async def _verify_asymmetric(self, token: str, header: dict[str, Any]) -> SupabasePrincipal:
        kid = header.get("kid")
        algorithm = str(header.get("alg"))

        key_set = await self._jwks_set()
        signing_key: PyJWK | None = None
        for candidate in key_set.keys:
            if candidate.key_id == kid:
                signing_key = candidate
                break
        if signing_key is None:
            # The kid is unknown - almost always a rotated key. Refresh once
            # before rejecting, otherwise a legitimate user is logged out by a
            # routine key rotation.
            key_set = await self._jwks_set(force=True)
            for candidate in key_set.keys:
                if candidate.key_id == kid:
                    signing_key = candidate
                    break
        if signing_key is None:
            raise UnauthorizedError("Unknown signing key. Please sign in again.")

        try:
            claims = jwt.decode(
                token,
                signing_key.key,
                algorithms=[algorithm],
                audience="authenticated",
                options={"require": ["exp", "sub"], "verify_aud": True},
            )
        except InvalidTokenError as exc:
            raise UnauthorizedError("Your session has expired. Please sign in again.") from exc
        return self._principal(claims)

    def _principal(self, claims: dict[str, Any]) -> SupabasePrincipal:
        subject = claims.get("sub")
        try:
            user_id = uuid.UUID(str(subject))
        except (TypeError, ValueError) as exc:
            raise UnauthorizedError("Token subject is not a valid user id.") from exc
        email = claims.get("email")
        return SupabasePrincipal(
            user_id=user_id,
            email=str(email) if email else None,
            claims=claims,
        )


# ---------------------------------------------------------------------------
# Razorpay
# ---------------------------------------------------------------------------
def verify_razorpay_payment_signature(
    *,
    razorpay_order_id: str,
    razorpay_payment_id: str,
    signature: str,
    key_secret: str,
) -> bool:
    """Check the signature Razorpay Checkout returns to the browser.

    The signed payload is exactly ``"<order_id>|<payment_id>"``. If either value
    were attacker-controlled and the signature still verified, the attacker
    would have to know ``key_secret`` - which is the entire point.
    """
    if not razorpay_order_id or not razorpay_payment_id or not signature:
        return False
    expected = hmac.new(
        key_secret.encode("utf-8"),
        f"{razorpay_order_id}|{razorpay_payment_id}".encode(),
        hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(expected, signature.strip())


def verify_razorpay_webhook_signature(
    *,
    body: bytes,
    signature: str | None,
    webhook_secret: str,
) -> bool:
    """Check the ``X-Razorpay-Signature`` header against the **raw** body.

    ``body`` must be the exact bytes received. Parsing to JSON and re-encoding
    changes key order and whitespace, producing a different digest and a
    legitimate webhook that fails verification.
    """
    if not signature or not webhook_secret:
        return False
    expected = hmac.new(
        webhook_secret.encode("utf-8"),
        body,
        hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(expected, signature.strip())


# ---------------------------------------------------------------------------
# Internal service tokens
# ---------------------------------------------------------------------------
#: Marks a token as belonging to this application's own key space, so it can
#: never be mistaken for (or replayed as) a Supabase user session.
_INTERNAL_TOKEN_TYPE = "internal"  # noqa: S105 - a token type tag, not a secret


def create_internal_token(
    *,
    settings: Settings,
    subject: str,
    purpose: str,
    ttl_seconds: int = 300,
    extra: dict[str, Any] | None = None,
) -> str:
    """Mint a short-lived token for internal use (worker hand-off, callbacks).

    Uses the application's own ``JWT_SECRET``, which is a different key space
    from Supabase's. Compromising a Supabase token therefore tells an attacker
    nothing about the signing key used here, and vice versa.
    """
    now = int(time.time())
    payload: dict[str, Any] = {
        "sub": subject,
        "purpose": purpose,
        "typ": _INTERNAL_TOKEN_TYPE,
        "iat": now,
        "nbf": now,
        "exp": now + ttl_seconds,
        "jti": uuid.uuid4().hex,
        **(extra or {}),
    }
    return jwt.encode(
        payload,
        settings.jwt_secret.get_secret_value(),
        algorithm=settings.jwt_algorithm,
    )


def verify_internal_token(
    token: str,
    *,
    settings: Settings,
    purpose: str,
) -> dict[str, Any]:
    """Validate an internal token and require the expected ``purpose``.

    The purpose claim is what stops a token minted for one job from being
    replayed against another endpoint.
    """
    try:
        claims = jwt.decode(
            token,
            settings.jwt_secret.get_secret_value(),
            algorithms=[settings.jwt_algorithm],
            options={"require": ["exp", "sub", "purpose"]},
        )
    except InvalidTokenError as exc:
        raise UnauthorizedError("Invalid or expired internal token.") from exc
    if claims.get("typ") != _INTERNAL_TOKEN_TYPE:
        raise UnauthorizedError("Invalid token type.")
    if claims.get("purpose") != purpose:
        raise UnauthorizedError("Token was not issued for this purpose.")
    return claims


# ---------------------------------------------------------------------------
# Request signing helpers
# ---------------------------------------------------------------------------
def sha256_hex(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def constant_time_equals(left: str, right: str) -> bool:
    return hmac.compare_digest(left.encode("utf-8"), right.encode("utf-8"))
