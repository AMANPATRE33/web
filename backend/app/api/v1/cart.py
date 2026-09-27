"""Cart endpoints.

## Identity

* **Signed in** - the cart belongs to `profiles.id` and survives anything.
* **Anonymous** - the cart belongs to a `sha256` of a 256-bit token held in an
  httpOnly cookie. The token is minted by this module on first contact.

There is no way to address another customer's cart. Lines are selected with
`WHERE cart_id = <the caller's own cart>` rather than loaded and then filtered,
so cross-cart access is unrepresentable rather than merely checked.

## Prices

Nothing in a request body is believed. `variant_id` and `quantity` go in; the
product, variant, material, size, price and stock come back out of the database.
`extra="forbid"` on the request models means a client that tries to send a price
gets a 422 instead of a silently-ignored field - which is the difference between
a clear failure and a future developer's misunderstanding.

## CSRF

Anonymous carts mutate via cookie, so they are exposed to cross-site POST. The
double-submit check is applied to every write. Signed-in requests arrive with a
bearer token from the server components, which a cross-origin page cannot forge,
so they are exempt - see `deps.require_csrf`.
"""

from __future__ import annotations

import uuid
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import AuthUser, OptionalUser, require_safe_write
from app.core.config import get_settings
from app.core.logging import get_logger
from app.db.session import get_db
from app.schemas.commerce import (
    CartItemAddRequest,
    CartItemUpdateRequest,
    CartLineResponse,
    CartMergeResponse,
    CartResponse,
    CartTotalsResponse,
)
from app.schemas.common import Money
from app.services import cart as cart_service
from app.services.pricing import format_rate_bps

logger = get_logger(__name__)

router = APIRouter(prefix="/cart", tags=["cart"])


# ---------------------------------------------------------------------------
# Identity resolution
# ---------------------------------------------------------------------------
class CartOwner:
    """The caller's cart, plus the token bookkeeping a guest needs."""

    __slots__ = ("cart", "guest_token", "is_new_token")

    def __init__(self, cart: Any, guest_token: str | None, is_new_token: bool) -> None:
        self.cart = cart
        self.guest_token = guest_token
        self.is_new_token = is_new_token


def _read_guest_token(request: Request) -> str | None:
    return request.cookies.get(cart_service.COOKIE_NAME)


def _set_guest_cookie(response: Response, token: str) -> None:
    """Persist the guest cart token.

    httpOnly so script on the page cannot read it, SameSite=Lax so it is not
    attached to cross-site POSTs (belt and braces alongside the CSRF check),
    Secure in production so it never crosses plaintext, and a long Max-Age
    because an abandoned-but-returning cart is the case worth keeping.
    """
    response.set_cookie(
        key=cart_service.COOKIE_NAME,
        value=token,
        max_age=60 * 60 * 24 * 30,
        httponly=True,
        samesite="lax",
        secure=get_settings().is_production,
        path="/",
    )


async def _resolve_owner(
    request: Request,
    response: Response,
    session: AsyncSession,
    user: OptionalUser,
) -> CartOwner:
    """Find the caller's cart, minting a guest token if they have neither."""
    if user is not None:
        cart = await cart_service.get_or_create_cart(session, profile_id=user.id)
        return CartOwner(cart=cart, guest_token=None, is_new_token=False)

    token = _read_guest_token(request)
    minted = token is None
    if token is None:
        token = cart_service.new_guest_token()
        _set_guest_cookie(response, token)

    cart = await cart_service.get_or_create_cart(session, guest_token=token)
    return CartOwner(cart=cart, guest_token=token, is_new_token=minted)


# ---------------------------------------------------------------------------
# Serialisation
# ---------------------------------------------------------------------------
def _to_line_response(view_line: Any) -> CartLineResponse:
    attributes = view_line.attributes or {}
    return CartLineResponse(
        id=view_line.cart_item_id,
        variant_id=view_line.variant_id,
        product_id=view_line.product_id,
        product_slug=view_line.product_slug,
        product_title=view_line.product_title,
        variant_title=view_line.variant_title,
        sku=view_line.sku,
        material=attributes.get("Material"),
        size=attributes.get("Size"),
        image_url=view_line.image_url,
        unit_price=Money.build(view_line.unit_price),
        compare_at_price=(
            Money.build(view_line.compare_at_price)
            if view_line.compare_at_price is not None
            else None
        ),
        line_total=Money.build(view_line.line_total),
        quantity=view_line.quantity,
        available=view_line.available,
        is_purchasable=view_line.is_purchasable,
        blocked_reason=view_line.blocked_reason,
    )


def _to_response(owner: CartOwner, view: Any) -> CartResponse:
    totals = view.totals
    shipping = totals.shipping

    return CartResponse(
        id=owner.cart.id,
        owner="account" if owner.cart.profile_id is not None else "guest",
        status=owner.cart.status.value,
        lines=[_to_line_response(line) for line in view.lines],
        totals=CartTotalsResponse(
            subtotal=Money.build(totals.subtotal),
            discount=Money.build(totals.discount_total),
            shipping=Money.build(totals.shipping_total),
            tax=Money.build(totals.tax_total),
            total=Money.build(totals.total),
            item_count=totals.item_count,
            is_estimate=True,
            tax_rate=format_rate_bps(totals.tax_rate_bps),
            tax_inclusive=totals.tax_inclusive,
            igst=Money.build(totals.igst),
            cgst=Money.build(totals.cgst),
            sgst=Money.build(totals.sgst),
            free_shipping_applied=bool(shipping and shipping.free_applied),
            shipping_estimate_days_min=shipping.estimated_days_min if shipping else None,
            shipping_estimate_days_max=shipping.estimated_days_max if shipping else None,
        ),
        blocking=list(totals.blocking),
        updated_at=owner.cart.updated_at,
    )


# ---------------------------------------------------------------------------
# Read
# ---------------------------------------------------------------------------
@router.get(
    "",
    response_model=CartResponse,
    summary="Read the current cart",
    description=(
        "Returns a fully resolved cart: product, variant, material, size, price "
        "and stock are read from the database at request time. The response is "
        "the authority on what the customer will pay."
    ),
)
async def read_cart(
    request: Request,
    response: Response,
    session: Annotated[AsyncSession, Depends(get_db)],
    user: OptionalUser,
) -> CartResponse:
    owner = await _resolve_owner(request, response, session, user)
    view = await cart_service.price_cart(session, owner.cart)
    await cart_service.touch(session, owner.cart.id)
    await session.commit()
    return _to_response(owner, view)


# ---------------------------------------------------------------------------
# Write
# ---------------------------------------------------------------------------
@router.post(
    "/items",
    response_model=CartResponse,
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(require_safe_write)],
    summary="Add a variant to the cart",
    description=(
        "Body carries `variant_id`, `quantity` and an optional non-price "
        "`added_from` hint. Nothing else is accepted. Adding a variant that is "
        "already in the cart merges into the existing line rather than creating "
        "a second one."
    ),
)
async def add_cart_item(
    payload: CartItemAddRequest,
    request: Request,
    response: Response,
    session: Annotated[AsyncSession, Depends(get_db)],
    user: OptionalUser,
) -> CartResponse:
    owner = await _resolve_owner(request, response, session, user)
    await cart_service.add_item(
        session,
        owner.cart,
        variant_id=payload.variant_id,
        quantity=payload.quantity,
        added_from=payload.added_from,
    )
    view = await cart_service.price_cart(session, owner.cart)
    await session.commit()
    return _to_response(owner, view)


@router.patch(
    "/items/{item_id}",
    response_model=CartResponse,
    dependencies=[Depends(require_safe_write)],
    summary="Set a cart line's quantity",
    description="Absolute, not a delta, so a retry is idempotent.",
)
async def update_cart_item(
    item_id: uuid.UUID,
    payload: CartItemUpdateRequest,
    request: Request,
    response: Response,
    session: Annotated[AsyncSession, Depends(get_db)],
    user: OptionalUser,
) -> CartResponse:
    owner = await _resolve_owner(request, response, session, user)
    await cart_service.update_item(session, owner.cart, item_id, payload.quantity)
    view = await cart_service.price_cart(session, owner.cart)
    await session.commit()
    return _to_response(owner, view)


@router.delete(
    "/items/{item_id}",
    response_model=CartResponse,
    dependencies=[Depends(require_safe_write)],
    summary="Remove a cart line",
)
async def remove_cart_item(
    item_id: uuid.UUID,
    request: Request,
    response: Response,
    session: Annotated[AsyncSession, Depends(get_db)],
    user: OptionalUser,
) -> CartResponse:
    owner = await _resolve_owner(request, response, session, user)
    await cart_service.remove_item(session, owner.cart, item_id)
    view = await cart_service.price_cart(session, owner.cart)
    await session.commit()
    return _to_response(owner, view)


@router.delete(
    "",
    response_model=CartResponse,
    dependencies=[Depends(require_safe_write)],
    summary="Empty the cart",
)
async def clear_cart(
    request: Request,
    response: Response,
    session: Annotated[AsyncSession, Depends(get_db)],
    user: OptionalUser,
) -> CartResponse:
    owner = await _resolve_owner(request, response, session, user)
    await cart_service.clear(session, owner.cart)
    view = await cart_service.price_cart(session, owner.cart)
    await session.commit()
    return _to_response(owner, view)


# ---------------------------------------------------------------------------
# Guest -> account merge
# ---------------------------------------------------------------------------
@router.post(
    "/merge",
    response_model=CartMergeResponse,
    dependencies=[Depends(require_safe_write)],
    summary="Fold a guest cart into the signed-in customer's cart",
    description=(
        "Call once, immediately after sign-in, with the guest cookie still "
        "present. Variants present in both carts are merged into one line and "
        "every line is revalidated against live stock. Adjustments are returned "
        "rather than applied silently. The guest cart is retired, so replaying "
        "this cannot duplicate anything."
    ),
)
async def merge_cart(
    request: Request,
    response: Response,
    session: Annotated[AsyncSession, Depends(get_db)],
    user: AuthUser,
) -> CartMergeResponse:
    token = _read_guest_token(request)
    if not token:
        # Nothing to merge. Not an error: most sign-ins have no guest cart.
        cart = await cart_service.get_or_create_cart(session, profile_id=user.id)
        view = await cart_service.price_cart(session, cart)
        await session.commit()
        return CartMergeResponse(cart=_to_response(CartOwner(cart, None, False), view))

    cart, merged, adjusted = await cart_service.merge_into_account(
        session, guest_token=token, profile_id=user.id
    )
    view = await cart_service.price_cart(session, cart)
    await session.commit()

    # The guest token has done its job. Clear it so it cannot be replayed to
    # re-merge, and so a shared machine does not leak the previous identity.
    response.delete_cookie(
        cart_service.COOKIE_NAME, path="/", samesite="lax"
    )

    return CartMergeResponse(
        cart=_to_response(CartOwner(cart, None, False), view),
        merged_variants=merged,
        adjusted=[
            {
                "variant_id": variant_id,
                "sku": sku,
                "requested": requested,
                "kept": kept,
                "reason": reason,
            }
            for variant_id, sku, requested, kept, reason in adjusted
        ],
    )


# ---------------------------------------------------------------------------
# Count (header badge)
# ---------------------------------------------------------------------------
@router.get(
    "/count",
    summary="Unit count for the header badge",
    description=(
        "A single aggregate. Kept separate from the full cart read so the header "
        "can render on every page without pulling the whole cart graph."
    ),
)
async def cart_count(
    request: Request,
    response: Response,
    session: Annotated[AsyncSession, Depends(get_db)],
    user: OptionalUser,
) -> dict[str, int | str]:
    owner = await _resolve_owner(request, response, session, user)
    count = await cart_service.cart_item_count(session, owner.cart.id)
    await session.commit()
    return {"count": count, "owner": "account" if owner.cart.profile_id else "guest"}


__all__ = ["router"]
