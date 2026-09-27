"""Session and account endpoints.

Sign-in, sign-up, email verification and password reset are performed by
Supabase Auth **directly from the browser**. This module deliberately exposes no
``/login`` or ``/signup`` endpoint that accepts a password, so a plaintext
credential has no path into the application process at all.

What this API owns is the *authoritative view* of the session: it verifies the
token Supabase issued, resolves the role from the database, and hands back the
profile that the rest of the application authorises against.
"""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import (
    AuthUser,
    require_csrf,
)
from app.core.config import get_settings
from app.core.errors import ForbiddenError, NotFoundError
from app.core.logging import get_logger
from app.db.session import get_db
from app.models.identity import Address, Profile
from app.schemas.auth import (
    AddressCreateRequest,
    AddressResponse,
    AddressUpdateRequest,
    ProfileUpdateRequest,
    SessionResponse,
    SessionUser,
)
from app.services import audit

logger = get_logger(__name__)

router = APIRouter(tags=["account"])


# ---------------------------------------------------------------------------
# Session
# ---------------------------------------------------------------------------
@router.get(
    "/session",
    response_model=SessionResponse,
    summary="Current session",
    description="Returns the authenticated profile and its authoritative role.",
)
async def read_session(user: AuthUser) -> SessionResponse:
    profile = user.profile
    token_role = user.principal.token_role
    return SessionResponse(
        user=SessionUser(
            id=profile.id,
            email=profile.email,
            full_name=profile.full_name,
            phone=profile.phone,
            role=profile.role.value,
            is_admin=profile.is_admin,
            email_verified=profile.email_verified_at is not None,
            created_at=profile.created_at,
        ),
        token_roles=[token_role] if token_role else [],
    )


@router.patch(
    "/profile",
    response_model=SessionUser,
    dependencies=[Depends(require_csrf)],
    summary="Update the signed-in profile",
    description=(
        "A customer may change their own name, phone number and marketing "
        "consent. Role and email are not writable here."
    ),
)
async def update_profile(
    payload: ProfileUpdateRequest,
    user: AuthUser,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> SessionUser:
    profile: Profile = user.profile
    changes: dict[str, Any] = {}

    for field in ("full_name", "phone", "marketing_opt_in"):
        value = getattr(payload, field)
        if value is not None and getattr(profile, field) != value:
            changes[field] = {"from": getattr(profile, field), "to": value}
            setattr(profile, field, value)

    if not changes:
        return _to_session_user(profile)

    await session.flush()
    await audit.record(
        session,
        actor=profile,
        action="profile.update",
        entity_type="profile",
        entity_id=str(profile.id),
        before=profile,
        after=profile,
    )
    await session.commit()
    return _to_session_user(profile)


def _to_session_user(profile: Profile) -> SessionUser:
    return SessionUser(
        id=profile.id,
        email=profile.email,
        full_name=profile.full_name,
        phone=profile.phone,
        role=profile.role.value,
        is_admin=profile.is_admin,
        email_verified=profile.email_verified_at is not None,
        created_at=profile.created_at,
    )


# ---------------------------------------------------------------------------
# Addresses
# ---------------------------------------------------------------------------
@router.get(
    "/addresses",
    response_model=list[AddressResponse],
    summary="List saved addresses",
)
async def list_addresses(
    user: AuthUser,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> list[AddressResponse]:
    result = await session.execute(
        select(Address)
        .where(Address.profile_id == user.id)
        .order_by(Address.is_default.desc(), Address.created_at.desc())
    )
    return [_to_address_response(a) for a in result.scalars().all()]


@router.post(
    "/addresses",
    response_model=AddressResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_csrf)],
    summary="Add an address",
)
async def create_address(
    payload: AddressCreateRequest,
    user: AuthUser,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> AddressResponse:
    existing_count = await _count_addresses(session, user.id)

    address = Address(
        profile_id=user.id,
        label=payload.label.strip() or "Home",
        full_name=payload.full_name.strip(),
        phone=payload.phone,
        line1=payload.line1.strip(),
        line2=payload.line2.strip() if payload.line2 else None,
        landmark=payload.landmark.strip() if payload.landmark else None,
        city=payload.city.strip(),
        state=payload.state.strip(),
        postal_code=payload.postal_code,
        country_code=payload.country_code.upper(),
        # The first address a customer saves is their default without having to
        # ask; a partial unique index guarantees only one default ever exists.
        is_default=True if (payload.is_default or existing_count == 0) else False,
    )
    session.add(address)
    await session.flush()

    if address.is_default:
        await _clear_other_defaults(session, user.id, address.id)
    await session.commit()
    await session.refresh(address)
    return _to_address_response(address)


@router.patch(
    "/addresses/{address_id}",
    response_model=AddressResponse,
    dependencies=[Depends(require_csrf)],
    summary="Update an address",
)
async def update_address(
    address_id: str,
    payload: AddressUpdateRequest,
    user: AuthUser,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> AddressResponse:
    address = await _get_own_address(session, user.id, address_id)

    for field, value in payload.model_dump(exclude_unset=True).items():
        if value is None:
            continue
        setattr(address, field, value.strip() if isinstance(value, str) else value)

    if payload.is_default:
        address.is_default = True
        await _clear_other_defaults(session, user.id, address.id)

    await session.commit()
    await session.refresh(address)
    return _to_address_response(address)


@router.delete(
    "/addresses/{address_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_csrf)],
    summary="Delete an address",
)
async def delete_address(
    address_id: str,
    user: AuthUser,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> Response:
    address = await _get_own_address(session, user.id, address_id)
    was_default = address.is_default
    await session.delete(address)  # AsyncSession.delete is a coroutine in SA 2.1
    await session.flush()

    # Never leave a customer without a default address.
    if was_default:
        replacement = await session.execute(
            select(Address)
            .where(Address.profile_id == user.id)
            .order_by(Address.created_at.asc())
            .limit(1)
        )
        next_best = replacement.scalar_one_or_none()
        if next_best is not None:
            next_best.is_default = True

    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/addresses/{address_id}/default",
    response_model=AddressResponse,
    dependencies=[Depends(require_csrf)],
    summary="Set the default address",
)
async def set_default_address(
    address_id: str,
    user: AuthUser,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> AddressResponse:
    address = await _get_own_address(session, user.id, address_id)
    address.is_default = True
    await _clear_other_defaults(session, user.id, address.id)
    await session.commit()
    await session.refresh(address)
    return _to_address_response(address)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
async def _count_addresses(session: AsyncSession, profile_id: object) -> int:
    result = await session.execute(select(Address.id).where(Address.profile_id == profile_id))
    return len(result.all())


async def _get_own_address(session: AsyncSession, profile_id: object, address_id: str) -> Address:
    result = await session.execute(
        select(Address).where(Address.id == address_id, Address.profile_id == profile_id)
    )
    address = result.scalar_one_or_none()
    if address is None:
        # Deliberately 404 rather than 403: a customer should not be able to
        # probe whether another customer's address id exists.
        raise NotFoundError("We could not find that address.", code="address_not_found")
    return address


async def _clear_other_defaults(session: AsyncSession, profile_id: object, keep_id: object) -> None:
    """Ensure at most one default address per profile.

    The partial unique index would also reject the violation, but clearing the
    others first means the write succeeds and the user sees the behaviour they
    asked for instead of a constraint error.
    """
    result = await session.execute(
        select(Address).where(
            Address.profile_id == profile_id,
            Address.id != keep_id,
            Address.is_default.is_(True),
        )
    )
    for other in result.scalars().all():
        other.is_default = False
    await session.flush()


def _to_address_response(address: Address) -> AddressResponse:
    return AddressResponse(
        id=address.id,
        label=address.label,
        full_name=address.full_name,
        phone=address.phone,
        line1=address.line1,
        line2=address.line2,
        landmark=address.landmark,
        city=address.city,
        state=address.state,
        postal_code=address.postal_code,
        country_code=address.country_code,
        is_default=address.is_default,
        created_at=address.created_at,
        updated_at=address.updated_at,
        one_line=address.one_line(),
    )


@router.get(
    "/auth-config",
    summary="Auth configuration for the frontend",
    description="Non-secret settings the sign-in page needs in order to call Supabase correctly.",
)
async def auth_config() -> dict[str, Any]:
    settings = get_settings()
    return {
        "providers": {"email": True, "google": False, "apple": False},
        "email_confirmation_required": settings.is_production,
        "redirect_urls": settings.redirect_url_list,
        "site_url": settings.frontend_url,
        "csrf": {
            "header": "X-CSRF-Token",
            "cookie": "csrf_token",
        },
    }


@router.get(
    "/session/verify",
    summary="Validate the current token",
    description=(
        "Cheap endpoint the frontend calls to decide whether a cached session is "
        "still usable, without a full page of account data."
    ),
)
async def verify_session(user: AuthUser) -> dict[str, Any]:
    expires_at = user.principal.claims.get("exp")
    return {
        "valid": True,
        "user_id": str(user.id),
        "role": user.profile.role.value,
        "expires_at": expires_at,
        "auth_method": "cookie" if user.via_cookie else "bearer",
    }


@router.post(
    "/logout",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_csrf)],
    summary="Record a client sign-out",
    description=(
        "Supabase signs the session out on the client. This endpoint exists so the "
        "sign-out is recorded server-side for the audit trail; it cannot invalidate "
        "an already-issued access token, which is why the frontend also calls "
        "supabase.auth.signOut()."
    ),
)
async def logout(user: AuthUser) -> Response:
    logger.info("client_signout", profile_id=str(user.id))
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get(
    "/admin-probe",
    include_in_schema=False,
)
async def admin_probe(user: AuthUser) -> dict[str, Any]:
    if not user.is_admin:
        raise ForbiddenError("Admin only.", code="admin_required")
    return {"ok": True, "role": user.role.value}
