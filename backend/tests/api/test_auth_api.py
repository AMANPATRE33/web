"""API-level authentication, authorisation and CSRF tests.

These exercise the trust boundaries end to end: an HTTP request goes in, and
the only thing that decides whether it is allowed is server-side state.
"""

from __future__ import annotations

import uuid
from typing import Any

import pytest
from app.models.enums import UserRole
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

pytestmark = [pytest.mark.integration, pytest.mark.api]


def _bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


# ---------------------------------------------------------------------------
# Anonymous access
# ---------------------------------------------------------------------------
class TestAnonymousAccess:
    async def test_session_requires_authentication(self, api_client: AsyncClient) -> None:
        response = await api_client.get("/api/v1/account/session")

        assert response.status_code == 401
        body = response.json()["error"]
        assert body["code"] == "unauthorized"
        # A useful message, but no internals.
        assert "Traceback" not in response.text
        assert "sqlalchemy" not in response.text.lower()

    async def test_addresses_require_authentication(self, api_client: AsyncClient) -> None:
        response = await api_client.get("/api/v1/account/addresses")
        assert response.status_code == 401

    async def test_auth_config_is_public(self, api_client: AsyncClient) -> None:
        """The sign-in page needs this before anyone has a session."""
        response = await api_client.get("/api/v1/account/auth-config")

        assert response.status_code == 200
        assert response.json()["csrf"]["header"] == "X-CSRF-Token"

    async def test_invalid_token_is_rejected(self, api_client: AsyncClient) -> None:
        response = await api_client.get(
            "/api/v1/account/session", headers=_bearer("garbage.token.value")
        )
        assert response.status_code == 401

    async def test_expired_token_is_rejected(self, api_client: AsyncClient, token_factory) -> None:
        """
        An expired token must not authenticate. The response is the generic
        "sign in again" message, because this route resolves the caller
        optionally and must not leak why a token was rejected.
        """
        token = token_factory(uuid.uuid4(), expires_in=-60)
        response = await api_client.get("/api/v1/account/session", headers=_bearer(token))
        assert response.status_code == 401
        assert response.json()["error"]["code"] == "unauthorized"


# ---------------------------------------------------------------------------
# Role based access control
# ---------------------------------------------------------------------------
class TestRoleBasedAccess:
    async def test_customer_is_identified_and_role_read_from_db(
        self, api_client: AsyncClient, make_profile, token_factory
    ) -> None:
        profile = await make_profile(role="CUSTOMER", full_name="Asha")

        response = await api_client.get(
            "/api/v1/account/session", headers=_bearer(token_factory(profile.id))
        )

        assert response.status_code == 200
        body = response.json()["user"]
        assert body["id"] == str(profile.id)
        assert body["role"] == "CUSTOMER"
        assert body["is_admin"] is False
        assert body["full_name"] == "Asha"

    async def test_customer_cannot_reach_admin_routes(
        self, api_client: AsyncClient, make_profile, token_factory
    ) -> None:
        profile = await make_profile(role="CUSTOMER")

        for path in (
            "/api/v1/admin/customers",
            "/api/v1/admin/customers/" + str(uuid.uuid4()),
        ):
            response = await api_client.get(path, headers=_bearer(token_factory(profile.id)))
            assert response.status_code == 403, path
            assert response.json()["error"]["code"] == "admin_required"

    async def test_admin_role_claim_in_token_is_ignored(
        self, api_client: AsyncClient, make_profile, token_factory
    ) -> None:
        """
        The core authorisation guarantee: a token that *claims* ADMIN does not
        grant admin access. Only the database row does.
        """
        profile = await make_profile(role="CUSTOMER")
        token = token_factory(
            profile.id, claims={"app_metadata": {"roles": ["ADMIN"]}, "role": "ADMIN"}
        )

        session_response = await api_client.get("/api/v1/account/session", headers=_bearer(token))
        assert session_response.json()["user"]["role"] == "CUSTOMER"
        assert session_response.json()["user"]["is_admin"] is False

        admin_response = await api_client.get("/api/v1/admin/customers", headers=_bearer(token))
        assert admin_response.status_code == 403

    async def test_admin_can_reach_admin_routes(
        self, api_client: AsyncClient, make_profile, token_factory
    ) -> None:
        admin = await make_profile(role="ADMIN", full_name="Store Admin")

        response = await api_client.get(
            "/api/v1/admin/customers", headers=_bearer(token_factory(admin.id))
        )

        assert response.status_code == 200
        assert "items" in response.json()

    async def test_role_change_takes_effect_on_the_next_request(
        self,
        api_client: AsyncClient,
        make_profile,
        token_factory,
        session: AsyncSession,
    ) -> None:
        """
        Revocation must not wait for token expiry. The same token that was
        refused a moment ago is accepted once the database row changes, and
        refused again if it is taken away - which is why authorisation reads
        the database instead of the token.
        """
        profile = await make_profile(role="CUSTOMER")
        token = token_factory(profile.id)

        assert (
            await api_client.get("/api/v1/admin/customers", headers=_bearer(token))
        ).status_code == 403

        profile.role = UserRole.ADMIN
        await session.commit()

        assert (
            await api_client.get("/api/v1/admin/customers", headers=_bearer(token))
        ).status_code == 200

        # ...and revoking it takes effect immediately, mid-session.
        profile.role = UserRole.CUSTOMER
        await session.commit()

        assert (
            await api_client.get("/api/v1/admin/customers", headers=_bearer(token))
        ).status_code == 403

    async def test_deactivated_account_is_rejected(
        self, api_client: AsyncClient, make_profile, token_factory
    ) -> None:
        profile = await make_profile(role="CUSTOMER", is_active=False)

        response = await api_client.get(
            "/api/v1/account/session", headers=_bearer(token_factory(profile.id))
        )

        assert response.status_code == 403
        assert response.json()["error"]["code"] == "account_deactivated"

    async def test_profile_is_created_on_first_authenticated_request(
        self, api_client: AsyncClient, token_factory
    ) -> None:
        """
        A user created outside the signup trigger (dashboard, future code path)
        must still get a profile, and must never get admin.
        """
        orphan_id = uuid.uuid4()
        token = token_factory(orphan_id, email="orphan@example.com")

        response = await api_client.get("/api/v1/account/session", headers=_bearer(token))

        assert response.status_code == 200
        body = response.json()["user"]
        assert body["id"] == str(orphan_id)
        assert body["role"] == "CUSTOMER"


# ---------------------------------------------------------------------------
# CSRF
# ---------------------------------------------------------------------------
class TestCsrfProtection:
    """
    Cookie-authenticated writes require a double-submit token. A bearer-token
    request does not, because a browser never attaches Authorization on its own.
    """

    async def test_bearer_write_does_not_require_csrf_token(
        self, api_client: AsyncClient, make_profile, token_factory
    ) -> None:
        profile = await make_profile()

        response = await api_client.post(
            "/api/v1/account/addresses",
            headers=_bearer(token_factory(profile.id)),
            json=_address_payload(),
        )

        assert response.status_code == 201, response.text

    async def test_cookie_write_without_csrf_header_is_rejected(
        self, api_client: AsyncClient, make_profile, token_factory
    ) -> None:
        profile = await make_profile()
        token = token_factory(profile.id)

        response = await api_client.post(
            "/api/v1/account/addresses",
            cookies={"sb-access-token": token},
            json=_address_payload(),
        )

        assert response.status_code == 403
        assert response.json()["error"]["code"] == "csrf_token_missing"

    async def test_cookie_write_with_mismatched_csrf_token_is_rejected(
        self, api_client: AsyncClient, make_profile, token_factory
    ) -> None:
        profile = await make_profile()
        token = token_factory(profile.id)

        response = await api_client.post(
            "/api/v1/account/addresses",
            cookies={"sb-access-token": token, "csrf_token": "expected-value"},
            headers={"X-CSRF-Token": "attacker-supplied-value"},
            json=_address_payload(),
        )

        assert response.status_code == 403
        assert response.json()["error"]["code"] == "csrf_token_invalid"

    async def test_cookie_write_with_matching_csrf_token_succeeds(
        self, api_client: AsyncClient, make_profile, token_factory
    ) -> None:
        profile = await make_profile()
        token = token_factory(profile.id)

        response = await api_client.post(
            "/api/v1/account/addresses",
            cookies={"sb-access-token": token, "csrf_token": "shared-value"},
            headers={"X-CSRF-Token": "shared-value"},
            json=_address_payload(),
        )

        assert response.status_code == 201, response.text

    async def test_cookie_read_does_not_require_csrf(
        self, api_client: AsyncClient, make_profile, token_factory
    ) -> None:
        """Reads are not state-changing, so no token is needed."""
        profile = await make_profile()

        response = await api_client.get(
            "/api/v1/account/session",
            cookies={"sb-access-token": token_factory(profile.id)},
        )

        assert response.status_code == 200

    async def test_base64_chunked_cookie_is_understood(
        self, api_client: AsyncClient, make_profile, token_factory
    ) -> None:
        """@supabase/ssr may split the session across base64url chunks."""
        import base64
        import json as json_lib

        profile = await make_profile()
        token = token_factory(profile.id)
        chunk = (
            base64.urlsafe_b64encode(json_lib.dumps({"access_token": token}).encode())
            .decode()
            .rstrip("=")
        )

        response = await api_client.get(
            "/api/v1/account/session",
            cookies={"sb-access-token": f"base64-{chunk}"},
        )

        assert response.status_code == 200


# ---------------------------------------------------------------------------
# Address ownership isolation
# ---------------------------------------------------------------------------
class TestAddressIsolation:
    async def test_customer_cannot_read_another_customers_address(
        self, api_client: AsyncClient, make_profile, token_factory
    ) -> None:
        owner = await make_profile()
        attacker = await make_profile()

        created = await api_client.post(
            "/api/v1/account/addresses",
            headers=_bearer(token_factory(owner.id)),
            json=_address_payload(),
        )
        assert created.status_code == 201
        address_id = created.json()["id"]

        response = await api_client.patch(
            f"/api/v1/account/addresses/{address_id}",
            headers=_bearer(token_factory(attacker.id)),
            json={"city": "Hijacked"},
        )

        # 404, not 403: a 403 would confirm the id exists.
        assert response.status_code == 404
        assert response.json()["error"]["code"] == "address_not_found"

    async def test_customer_cannot_delete_another_customers_address(
        self, api_client: AsyncClient, make_profile, token_factory
    ) -> None:
        owner = await make_profile()
        attacker = await make_profile()

        created = await api_client.post(
            "/api/v1/account/addresses",
            headers=_bearer(token_factory(owner.id)),
            json=_address_payload(),
        )
        address_id = created.json()["id"]

        response = await api_client.delete(
            f"/api/v1/account/addresses/{address_id}",
            headers=_bearer(token_factory(attacker.id)),
        )

        assert response.status_code == 404

    async def test_addresses_list_is_scoped_to_the_caller(
        self, api_client: AsyncClient, make_profile, token_factory
    ) -> None:
        owner = await make_profile()
        other = await make_profile()

        await api_client.post(
            "/api/v1/account/addresses",
            headers=_bearer(token_factory(owner.id)),
            json=_address_payload(),
        )

        response = await api_client.get(
            "/api/v1/account/addresses", headers=_bearer(token_factory(other.id))
        )

        assert response.status_code == 200
        assert response.json() == []


# ---------------------------------------------------------------------------
# Profile updates
# ---------------------------------------------------------------------------
class TestProfileUpdates:
    async def test_update_own_profile(
        self, api_client: AsyncClient, make_profile, token_factory
    ) -> None:
        profile = await make_profile()

        response = await api_client.patch(
            "/api/v1/account/profile",
            headers=_bearer(token_factory(profile.id)),
            json={"full_name": "New Name", "phone": "+91 98765 43210"},
        )

        assert response.status_code == 200
        assert response.json()["full_name"] == "New Name"
        assert response.json()["phone"] == "+919876543210"

    async def test_cannot_escalate_role_via_profile_update(
        self, api_client: AsyncClient, make_profile, token_factory
    ) -> None:
        profile = await make_profile(role="CUSTOMER")

        response = await api_client.patch(
            "/api/v1/account/profile",
            headers=_bearer(token_factory(profile.id)),
            # `extra="forbid"` on the schema rejects this outright.
            json={"role": "ADMIN"},
        )

        assert response.status_code == 422
        assert response.json()["error"]["code"] == "validation_error"

    async def test_invalid_phone_is_rejected_with_field_error(
        self, api_client: AsyncClient, make_profile, token_factory
    ) -> None:
        profile = await make_profile()

        response = await api_client.patch(
            "/api/v1/account/profile",
            headers=_bearer(token_factory(profile.id)),
            json={"phone": "not-a-phone"},
        )

        assert response.status_code == 422
        field_errors = response.json()["error"]["field_errors"]
        assert "phone" in field_errors


def _address_payload(**overrides: Any) -> dict[str, Any]:
    payload = {
        "label": "Home",
        "full_name": "Test Customer",
        "phone": "+91 98765 43210",
        "line1": "42 Residency Road",
        "line2": "Near the park",
        "city": "Pune",
        "state": "Maharashtra",
        "postal_code": "411001",
        "country_code": "IN",
    }
    payload.update(overrides)
    return payload
