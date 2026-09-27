"""Cryptographic verification tests.

Every one of these guards a trust boundary. A failure here means a forged
token, a forged payment, or a replayed webhook would be accepted.
"""

from __future__ import annotations

import json
import time
import uuid

import jwt
import pytest
from app.core.config import Settings, get_settings
from app.core.errors import UnauthorizedError
from app.core.security import (
    SupabaseTokenVerifier,
    constant_time_equals,
    create_internal_token,
    verify_internal_token,
    verify_razorpay_payment_signature,
    verify_razorpay_webhook_signature,
)

pytestmark = pytest.mark.unit

JWT_SECRET = "unit-test-supabase-jwt-secret-value-0123456789"


def _settings(**overrides) -> Settings:
    base = {
        "supabase_url": "https://project.supabase.co",
        "supabase_jwt_secret": JWT_SECRET,
        "supabase_publishable_key": "sb_publishable_test",
        "jwt_secret": "unit-test-internal-signing-secret-0123456789",
        "jwt_algorithm": "HS256",
        "cors_origins": "http://localhost:3000",
    }
    base.update(overrides)
    return Settings(**base)


def _token(
    *,
    user_id: uuid.UUID | None = None,
    secret: str = JWT_SECRET,
    expires_in: int = 3600,
    audience: str | None = "authenticated",
    algorithm: str = "HS256",
    extra: dict | None = None,
    omit_exp: bool = False,
) -> str:
    now = int(time.time())
    payload: dict = {
        "sub": str(user_id or uuid.uuid4()),
        "email": "customer@example.com",
        "iat": now,
    }
    if not omit_exp:
        payload["exp"] = now + expires_in
    if audience is not None:
        payload["aud"] = audience
    if extra:
        payload.update(extra)
    return jwt.encode(payload, secret, algorithm=algorithm)


# ---------------------------------------------------------------------------
# Supabase access tokens
# ---------------------------------------------------------------------------
class TestSupabaseTokenVerifier:
    async def test_valid_token_is_accepted(self) -> None:
        verifier = SupabaseTokenVerifier(_settings())
        user_id = uuid.uuid4()

        principal = await verifier.verify(_token(user_id=user_id))

        assert principal.user_id == user_id
        assert principal.email == "customer@example.com"

    async def test_token_signed_with_wrong_secret_is_rejected(self) -> None:
        verifier = SupabaseTokenVerifier(_settings())

        with pytest.raises(UnauthorizedError):
            await verifier.verify(_token(secret="attacker-guessed-secret"))

    async def test_tampered_payload_is_rejected(self) -> None:
        """Flipping a claim invalidates the signature."""
        verifier = SupabaseTokenVerifier(_settings())
        token = _token()
        header, payload, signature = token.split(".")

        claims = json.loads(jwt.utils.base64url_decode(payload + "=" * (-len(payload) % 4)))
        # Escalate to admin in the payload, keeping the original signature.
        claims["role"] = "ADMIN"
        forged_payload = (
            jwt.utils.base64url_encode(json.dumps(claims).encode("utf-8"))
            .decode("utf-8")
            .rstrip("=")
        )

        with pytest.raises(UnauthorizedError):
            await verifier.verify(f"{header}.{forged_payload}.{signature}")

    async def test_expired_token_is_rejected(self) -> None:
        verifier = SupabaseTokenVerifier(_settings())

        with pytest.raises(UnauthorizedError, match="expired"):
            await verifier.verify(_token(expires_in=-120))

    async def test_wrong_audience_is_rejected(self) -> None:
        """A token minted for the `anon` role must not authenticate a user."""
        verifier = SupabaseTokenVerifier(_settings())

        with pytest.raises(UnauthorizedError):
            await verifier.verify(_token(audience="anon"))

    async def test_token_without_expiry_is_rejected(self) -> None:
        verifier = SupabaseTokenVerifier(_settings())

        with pytest.raises(UnauthorizedError):
            await verifier.verify(_token(omit_exp=True))

    async def test_garbage_token_is_rejected(self) -> None:
        verifier = SupabaseTokenVerifier(_settings())

        for candidate in ("", "not-a-jwt", "a.b", "a.b.c.d.e"):
            with pytest.raises(UnauthorizedError):
                await verifier.verify(candidate)

    async def test_non_uuid_subject_is_rejected(self) -> None:
        verifier = SupabaseTokenVerifier(_settings())
        now = int(time.time())
        token = jwt.encode(
            {"sub": "not-a-uuid", "exp": now + 60, "aud": "authenticated"},
            JWT_SECRET,
            algorithm="HS256",
        )

        with pytest.raises(UnauthorizedError):
            await verifier.verify(token)

    async def test_algorithm_none_is_rejected(self) -> None:
        """The classic `alg: none` bypass must not be accepted."""
        verifier = SupabaseTokenVerifier(_settings())
        now = int(time.time())
        header = (
            jwt.utils.base64url_encode(json.dumps({"alg": "none", "typ": "JWT"}).encode())
            .decode()
            .rstrip("=")
        )
        payload = (
            jwt.utils.base64url_encode(
                json.dumps(
                    {"sub": str(uuid.uuid4()), "exp": now + 600, "aud": "authenticated"}
                ).encode()
            )
            .decode()
            .rstrip("=")
        )

        with pytest.raises(UnauthorizedError):
            await verifier.verify(f"{header}.{payload}.")

    async def test_asymmetric_token_rejected_when_no_jwks_configured(self) -> None:
        """With no secret and no reachable JWKS, verification must fail closed."""
        verifier = SupabaseTokenVerifier(
            _settings(supabase_jwt_secret=None, supabase_url="http://127.0.0.1:9")
        )
        now = int(time.time())
        token = jwt.encode(
            {"sub": str(uuid.uuid4()), "exp": now + 60, "aud": "authenticated"},
            "x",
            algorithm="HS256",
        )
        # Header says HS256 but no secret is configured, so it must not fall
        # back to verifying with an empty key.
        with pytest.raises(UnauthorizedError):
            await verifier.verify(token)

    async def test_token_role_is_reported_but_not_trusted(self) -> None:
        """The role claim is surfaced for debugging, clearly separated from truth."""
        verifier = SupabaseTokenVerifier(_settings())
        token = _token(
            extra={"app_metadata": {"roles": ["ADMIN"]}},
        )

        principal = await verifier.verify(token)

        # Reported...
        assert principal.token_role == "ADMIN"
        # ...but the principal itself carries no authorisation decision.
        assert not hasattr(principal, "is_admin")


# ---------------------------------------------------------------------------
# Razorpay
# ---------------------------------------------------------------------------
class TestRazorpayPaymentSignature:
    KEY_SECRET = "razorpay_key_secret_for_tests"

    def test_valid_signature_accepted(self) -> None:
        import hashlib
        import hmac

        order_id, payment_id = "order_ABC123", "pay_XYZ789"
        expected = hmac.new(
            self.KEY_SECRET.encode(),
            f"{order_id}|{payment_id}".encode(),
            hashlib.sha256,
        ).hexdigest()

        assert verify_razorpay_payment_signature(
            razorpay_order_id=order_id,
            razorpay_payment_id=payment_id,
            signature=expected,
            key_secret=self.KEY_SECRET,
        )

    def test_signature_for_a_different_payment_is_rejected(self) -> None:
        """The classic replay: a valid signature reused on another payment."""
        import hashlib
        import hmac

        order_id = "order_ABC123"
        signature = hmac.new(
            self.KEY_SECRET.encode(),
            f"{order_id}|pay_legit".encode(),
            hashlib.sha256,
        ).hexdigest()

        assert not verify_razorpay_payment_signature(
            razorpay_order_id=order_id,
            razorpay_payment_id="pay_attacker",
            signature=signature,
            key_secret=self.KEY_SECRET,
        )

    def test_signature_with_wrong_secret_rejected(self) -> None:
        assert not verify_razorpay_payment_signature(
            razorpay_order_id="order_1",
            razorpay_payment_id="pay_1",
            signature="deadbeef",
            key_secret=self.KEY_SECRET,
        )

    def test_empty_inputs_rejected(self) -> None:
        assert not verify_razorpay_payment_signature(
            razorpay_order_id="",
            razorpay_payment_id="pay_1",
            signature="abc",
            key_secret=self.KEY_SECRET,
        )
        assert not verify_razorpay_payment_signature(
            razorpay_order_id="order_1",
            razorpay_payment_id="pay_1",
            signature="",
            key_secret=self.KEY_SECRET,
        )

    def test_signature_covers_both_identifiers(self) -> None:
        """Swapping order and payment ids must invalidate the signature."""
        import hashlib
        import hmac

        signature = hmac.new(
            self.KEY_SECRET.encode(),
            b"order_A|pay_B",
            hashlib.sha256,
        ).hexdigest()

        assert not verify_razorpay_payment_signature(
            razorpay_order_id="pay_B",
            razorpay_payment_id="order_A",
            signature=signature,
            key_secret=self.KEY_SECRET,
        )


class TestRazorpayWebhookSignature:
    SECRET = "webhook_secret_for_tests"

    def test_valid_webhook_signature_accepted(self) -> None:
        import hashlib
        import hmac

        body = b'{"event":"payment.captured","payload":{}}'
        signature = hmac.new(self.SECRET.encode(), body, hashlib.sha256).hexdigest()

        assert verify_razorpay_webhook_signature(
            body=body, signature=signature, webhook_secret=self.SECRET
        )

    def test_reserialised_body_is_rejected(self) -> None:
        """
        The signature is over raw bytes. A body that was parsed and re-encoded
        is a different byte sequence and must fail - which is why the webhook
        route must read the raw request body rather than a parsed model.
        """
        import hashlib
        import hmac

        # Pretty-printed, as most HTTP clients and proxies would deliver it.
        original = json.dumps(
            {"event": "payment.captured", "payload": {"entity": {"amount": 100}}},
            indent=2,
        ).encode()
        signature = hmac.new(self.SECRET.encode(), original, hashlib.sha256).hexdigest()
        reserialised = json.dumps(json.loads(original), separators=(",", ":")).encode()

        assert reserialised != original, "test premise: bytes must actually differ"
        assert not verify_razorpay_webhook_signature(
            body=reserialised, signature=signature, webhook_secret=self.SECRET
        )

    def test_tampered_body_rejected(self) -> None:
        import hashlib
        import hmac

        body = b'{"amount":100}'
        signature = hmac.new(self.SECRET.encode(), body, hashlib.sha256).hexdigest()

        assert not verify_razorpay_webhook_signature(
            body=b'{"amount":1}', signature=signature, webhook_secret=self.SECRET
        )

    def test_missing_signature_or_secret_rejected(self) -> None:
        assert not verify_razorpay_webhook_signature(
            body=b"{}", signature=None, webhook_secret=self.SECRET
        )
        assert not verify_razorpay_webhook_signature(body=b"{}", signature="abc", webhook_secret="")


# ---------------------------------------------------------------------------
# Internal tokens
# ---------------------------------------------------------------------------
class TestInternalTokens:
    def test_round_trip(self) -> None:
        settings = _settings()

        token = create_internal_token(
            settings=settings, subject="worker", purpose="outbox", ttl_seconds=60
        )
        claims = verify_internal_token(token, settings=settings, purpose="outbox")

        assert claims["sub"] == "worker"
        assert claims["purpose"] == "outbox"

    def test_wrong_purpose_rejected(self) -> None:
        """A token minted for one job must not authorise another endpoint."""
        settings = _settings()
        token = create_internal_token(
            settings=settings, subject="worker", purpose="outbox", ttl_seconds=60
        )

        with pytest.raises(UnauthorizedError, match="not issued for this purpose"):
            verify_internal_token(token, settings=settings, purpose="refund")

    def test_expired_internal_token_rejected(self) -> None:
        settings = _settings()
        token = create_internal_token(
            settings=settings, subject="worker", purpose="outbox", ttl_seconds=-10
        )

        with pytest.raises(UnauthorizedError):
            verify_internal_token(token, settings=settings, purpose="outbox")

    async def test_token_signed_with_our_own_key_does_not_authenticate_a_user(self) -> None:
        """
        Key-space separation: the internal signing key is not Supabase's, so an
        internally minted token can never be replayed as a user session.
        """
        settings = _settings()
        token = create_internal_token(
            settings=settings, subject=str(uuid.uuid4()), purpose="outbox", ttl_seconds=60
        )

        verifier = SupabaseTokenVerifier(settings)
        with pytest.raises(UnauthorizedError):
            await verifier.verify(token)


def test_constant_time_equals() -> None:
    assert constant_time_equals("abc", "abc")
    assert not constant_time_equals("abc", "abd")
    assert not constant_time_equals("abc", "abcd")


def test_production_settings_reject_placeholder_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    """The safety rails must actually refuse an unsafe production config."""
    get_settings.cache_clear()
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("JWT_SECRET", "change-me-to-48-random-characters-minimum")

    try:
        with pytest.raises(ValueError, match="production"):
            Settings()
    finally:
        get_settings.cache_clear()
