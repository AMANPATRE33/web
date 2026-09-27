"""Admin-only account management.

Every route in this module is protected by ``require_admin``, which re-reads
``profiles.role`` from the database on each request. The router additionally
carries the dependency at router level so that adding a new endpoint cannot
accidentally ship without authorisation - the failure mode this is designed to
prevent is a new route that is easy to forget to guard.
"""

from __future__ import annotations

import uuid
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Request, Response, status
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import AdminUser, get_current_admin
from app.core.errors import ConflictError, NotFoundError, ValidationError
from app.core.logging import get_logger
from app.db.session import get_db
from app.models.enums import UserRole
from app.models.identity import Profile
from app.schemas.auth import (
    AdminCreateUserRequest,
    AdminRoleUpdateRequest,
    AdminUserListResponse,
    AdminUserResponse,
    PasswordResetAdminRequest,
)
from app.services import audit
from app.services.supabase_auth import SupabaseAuthService, get_auth_service

logger = get_logger(__name__)

#: Router-level guard. New endpoints added below are protected automatically.
#: The dependency *function* is required here, not the `AdminUser` alias: passing
#: an Annotated alias into Depends() makes FastAPI treat it as a query parameter
#: rather than a dependency.
router = APIRouter(
    prefix="/admin",
    tags=["admin"],
    dependencies=[Depends(get_current_admin)],
)


@router.get(
    "/customers",
    response_model=AdminUserListResponse,
    summary="List customers",
    description="Paginated customer list with order counts and lifetime value.",
)
async def list_customers(
    admin: AdminUser,
    session: Annotated[AsyncSession, Depends(get_db)],
    page: int = 1,
    per_page: int = 25,
    search: str | None = None,
) -> AdminUserListResponse:
    per_page = max(1, min(per_page, 100))
    page = max(1, page)

    from app.models.orders import Order, OrderStatus

    order_stats = (
        select(
            Order.profile_id.label("profile_id"),
            func.count(Order.id).label("order_count"),
            func.coalesce(func.sum(Order.total), 0).label("lifetime_value"),
        )
        .where(Order.status != OrderStatus.CANCELLED)
        .group_by(Order.profile_id)
        .subquery()
    )

    stmt = select(
        Profile,
        func.coalesce(order_stats.c.order_count, 0).label("order_count"),
        func.coalesce(order_stats.c.lifetime_value, 0).label("lifetime_value"),
    ).outerjoin(order_stats, order_stats.c.profile_id == Profile.id)

    if search:
        needle = f"%{search.strip().lower()}%"
        stmt = stmt.where(
            or_(
                func.lower(Profile.email).like(needle),
                func.lower(func.coalesce(Profile.full_name, "")).like(needle),
                func.lower(func.coalesce(Profile.phone, "")).like(needle),
            )
        )

    total = await session.execute(
        select(func.count()).select_from(
            stmt.with_only_columns(Profile.id).order_by(None).subquery()
        )
    )

    rows = await session.execute(
        stmt.order_by(Profile.created_at.desc()).offset((page - 1) * per_page).limit(per_page)
    )
    customers = rows.all()

    return AdminUserListResponse(
        items=[
            _to_response(profile, order_count=order_count, lifetime_value=lifetime_value)
            for profile, order_count, lifetime_value in customers
        ],
        total=total.scalar_one(),
        page=page,
        per_page=per_page,
    )


@router.get(
    "/customers/{customer_id}",
    response_model=AdminUserResponse,
    summary="Customer detail",
)
async def get_customer(
    customer_id: uuid.UUID,
    admin: AdminUser,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> AdminUserResponse:
    profile = await _load_profile(session, customer_id)
    return _to_response(profile)


@router.post(
    "/customers",
    response_model=AdminUserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a customer account",
    description=(
        "Support-assisted signup. The password is forwarded to Supabase Auth over "
        "TLS and never written to this application's database or logs."
    ),
)
async def create_customer(
    payload: AdminCreateUserRequest,
    request: Request,
    admin: AdminUser,
    session: Annotated[AsyncSession, Depends(get_db)],
    auth_service: Annotated[SupabaseAuthService, Depends(get_auth_service)],
) -> AdminUserResponse:
    existing = await auth_service.find_user_by_email(str(payload.email))
    if existing is not None:
        raise ConflictError(
            "An account with that email already exists.",
            code="email_already_registered",
        )

    managed = await auth_service.create_user(
        email=str(payload.email),
        password=payload.password,
        email_confirm=payload.email_confirm,
        user_metadata={
            "full_name": payload.full_name,
            "phone": payload.phone,
            # Recorded in Supabase metadata for reference only. The database
            # column is what authorises anything.
            "created_by_admin": str(admin.id),
        },
    )

    profile = Profile(
        id=managed.id,
        email=managed.email,
        full_name=payload.full_name,
        phone=payload.phone,
        role=UserRole(payload.role),
        email_verified_at=_now() if payload.email_confirm else None,
    )
    session.add(profile)
    await session.flush()

    await audit.record(
        session,
        action="customer.create",
        entity_type="profile",
        entity_id=str(profile.id),
        actor=admin.profile,
        after=profile,
        request=request,
    )
    await session.commit()
    return _to_response(profile)


@router.patch(
    "/customers/{customer_id}/role",
    response_model=AdminUserResponse,
    summary="Change a customer's role",
    description=(
        "Grants or revokes staff access. Revocation takes effect on the very next "
        "request because authorisation re-reads the role from the database rather "
        "than from the access token."
    ),
)
async def update_role(
    customer_id: uuid.UUID,
    payload: AdminRoleUpdateRequest,
    request: Request,
    admin: AdminUser,
    session: Annotated[AsyncSession, Depends(get_db)],
    auth_service: Annotated[SupabaseAuthService, Depends(get_auth_service)],
) -> AdminUserResponse:
    profile = await _load_profile(session, customer_id)

    if profile.id == admin.id and payload.role != UserRole.ADMIN:
        raise ValidationError(
            "You cannot remove your own admin access.",
            code="cannot_demote_self",
        )

    previous = profile.role
    profile.role = payload.role
    await session.flush()

    # Keep the Supabase claim in step so the dashboard can read it, but the
    # database remains the authority.
    try:
        await auth_service.update_user(
            profile.id,
            {"app_metadata": {"roles": [payload.role.value]}},
        )
    except Exception as exc:
        # The database change is the one that matters; a metadata sync failure
        # must not roll back a legitimate role change, but it must be visible.
        logger.error(
            "role_metadata_sync_failed",
            profile_id=str(profile.id),
            error=str(exc),
        )

    await audit.record(
        session,
        action="customer.role_change",
        entity_type="profile",
        entity_id=str(profile.id),
        actor=admin.profile,
        before={"role": previous.value},
        after={"role": payload.role.value},
        request=request,
    )
    await session.commit()
    return _to_response(profile)


@router.post(
    "/customers/{customer_id}/deactivate",
    response_model=AdminUserResponse,
    summary="Deactivate a customer",
)
async def deactivate_customer(
    customer_id: uuid.UUID,
    request: Request,
    admin: AdminUser,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> AdminUserResponse:
    profile = await _load_profile(session, customer_id)
    if profile.id == admin.id:
        raise ValidationError(
            "You cannot deactivate your own account.", code="cannot_deactivate_self"
        )
    if profile.role == UserRole.ADMIN:
        raise ConflictError(
            "Demote this account to a customer before deactivating it.",
            code="cannot_deactivate_admin",
        )

    profile.is_active = False
    profile.deactivated_at = _now()
    await session.flush()
    await audit.record(
        session,
        action="customer.deactivate",
        entity_type="profile",
        entity_id=str(profile.id),
        actor=admin.profile,
        after=profile,
        request=request,
    )
    await session.commit()
    return _to_response(profile)


@router.post(
    "/customers/{customer_id}/activate",
    response_model=AdminUserResponse,
    summary="Reactivate a customer",
)
async def activate_customer(
    customer_id: uuid.UUID,
    request: Request,
    admin: AdminUser,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> AdminUserResponse:
    profile = await _load_profile(session, customer_id)
    profile.is_active = True
    profile.deactivated_at = None
    await session.flush()
    await audit.record(
        session,
        action="customer.activate",
        entity_type="profile",
        entity_id=str(profile.id),
        actor=admin.profile,
        after=profile,
        request=request,
    )
    await session.commit()
    return _to_response(profile)


@router.post(
    "/customers/{customer_id}/password-reset",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Send a password reset email",
)
async def send_password_reset(
    customer_id: uuid.UUID,
    payload: PasswordResetAdminRequest,
    admin: AdminUser,
    session: Annotated[AsyncSession, Depends(get_db)],
    auth_service: Annotated[SupabaseAuthService, Depends(get_auth_service)],
) -> dict[str, Any]:
    profile = await _load_profile(session, customer_id)
    await auth_service.send_password_reset(profile.email, redirect_to=payload.redirect_to)
    logger.info("admin_password_reset", actor=str(admin.id), target=str(profile.id))
    return {"status": "accepted", "message": "If that account exists, a reset link has been sent."}


@router.delete(
    "/customers/{customer_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a customer account",
    description=(
        "Destructive. Prefer deactivation, which preserves order history and the "
        "FKs that depend on it. Requires an explicit confirmation query parameter."
    ),
)
async def delete_customer(
    customer_id: uuid.UUID,
    request: Request,
    admin: AdminUser,
    session: Annotated[AsyncSession, Depends(get_db)],
    auth_service: Annotated[SupabaseAuthService, Depends(get_auth_service)],
    confirm: bool = False,
) -> Response:
    if not confirm:
        raise ValidationError(
            "Pass ?confirm=true to delete a customer permanently.",
            code="confirmation_required",
        )

    profile = await _load_profile(session, customer_id)
    if profile.id == admin.id:
        raise ValidationError("You cannot delete your own account.", code="cannot_delete_self")
    if profile.role == UserRole.ADMIN:
        raise ConflictError("Demote this account before deleting it.", code="cannot_delete_admin")

    from app.models.orders import Order

    order_count = await session.execute(
        select(func.count(Order.id)).where(Order.profile_id == profile.id)
    )
    if (order_count.scalar_one() or 0) > 0:
        # orders.profile_id is ON DELETE RESTRICT precisely so an order can
        # never be orphaned; say so plainly instead of raising a raw FK error.
        raise ConflictError(
            "This customer has orders, which must be retained for accounting. "
            "Deactivate the account instead.",
            code="customer_has_orders",
        )

    await audit.record(
        session,
        action="customer.delete",
        entity_type="profile",
        entity_id=str(profile.id),
        actor=admin.profile,
        before=profile,
        request=request,
    )
    await session.delete(profile)  # coroutine in SQLAlchemy >= 2.1
    await session.commit()

    await auth_service.delete_user(profile.id, should_soft_delete=True)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
async def _load_profile(session: AsyncSession, profile_id: uuid.UUID) -> Profile:
    result = await session.execute(select(Profile).where(Profile.id == profile_id))
    profile = result.scalar_one_or_none()
    if profile is None:
        raise NotFoundError("We could not find that customer.", code="customer_not_found")
    return profile


def _now() -> Any:
    from datetime import UTC, datetime

    return datetime.now(UTC)


def _to_response(
    profile: Profile, *, order_count: int = 0, lifetime_value: int = 0
) -> AdminUserResponse:
    return AdminUserResponse(
        id=profile.id,
        email=profile.email,
        full_name=profile.full_name,
        phone=profile.phone,
        role=profile.role.value,
        is_active=profile.is_active,
        email_verified=profile.email_verified_at is not None,
        created_at=profile.created_at,
        last_login_at=profile.last_login_at,
    )
