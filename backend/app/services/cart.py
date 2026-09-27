"""The authoritative cart.

## The invariant

`carts` and `cart_items` hold **no prices at all**. A cart row is a variant id
and a quantity. Every figure a customer sees is recomputed from the catalogue on
read, by `price_cart`, through `services.pricing`.

This is the difference between a cart and a suggestion. If the cart stored a
total, that total would be either:

* **stale** - the catalogue price moved and the customer is shown a number
  nobody intends to honour, or
* **trusted** - the client can set it, because a client that can set a stored
  total can set it to zero.

Recomputing is cheap (a handful of indexed joins) and it means there is exactly
one place in the codebase where a cart total is produced, so the cart page, the
checkout page and the order that eventually gets written cannot disagree.

## What the client is allowed to say

`variant_id` and `quantity`. Nothing else. See `schemas/commerce.py`.

## Guest identity

A guest cart is identified by a high-entropy token in an httpOnly cookie. Only
`sha256(token)` is stored. Lookup is by hash, so it stays a single indexed
equality rather than a scan, and a database dump yields hashes that cannot be
replayed as cookies.

The token is minted by the API on first contact and rotated when an anonymous
cart is claimed by a sign-in, so a token observed before sign-in is useless
after it.
"""

from __future__ import annotations

import hashlib
import secrets
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload, selectinload

from app.core.config import get_settings
from app.core.errors import (
    InsufficientStockError,
    NotFoundError,
    ValidationError,
)
from app.core.logging import get_logger
from app.models.catalog import (
    Product,
    ProductVariant,
)
from app.models.commerce import Cart, CartItem
from app.models.enums import CartStatus, ProductStatus, VariantStatus
from app.services import inventory as inventory_service
from app.services.pricing import (
    PricedLine,
    Totals,
    build_priced_line,
    compute_totals,
    effective_unit_price,
)

logger = get_logger(__name__)

#: The `cart_items` CHECK constraints. Mirrored here so validation and the
#: database agree; if these ever drift, `tests/services/test_cart_service.py`
#: fails.
MAX_QUANTITY = 99
MIN_QUANTITY = 1

#: Bytes of entropy in a guest cart token. 32 bytes is not a value a human
#: guesses or a rainbow table reaches.
GUEST_TOKEN_BYTES = 32

COOKIE_NAME = "spp_cart"


# ---------------------------------------------------------------------------
# Guest tokens
# ---------------------------------------------------------------------------
def new_guest_token() -> str:
    """Mint a guest cart token. Returned to the client once, in a cookie."""
    return secrets.token_urlsafe(GUEST_TOKEN_BYTES)


def hash_guest_token(token: str) -> str:
    """Hash a guest token for storage and lookup.

    Plain SHA-256, not a slow KDF, and that is the right choice here: the input
    is 256 bits of CSPRNG output, so there is no dictionary to attack. A slow
    KDF would only add latency to every cart read.
    """
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# Resolution
# ---------------------------------------------------------------------------
async def get_or_create_cart(
    session: AsyncSession,
    *,
    profile_id: uuid.UUID | None = None,
    guest_token: str | None = None,
) -> Cart:
    """Return the caller's live cart, creating one if needed.

    Exactly one of `profile_id` / `guest_token` identifies the caller. Supplying
    both is a programming error, not something to silently resolve - a cart
    reachable two ways is a cross-account read, and the schema's
    `carts_exactly_one_owner` CHECK exists precisely because that was worth
    making unrepresentable.
    """
    if (profile_id is None) == (guest_token is None):
        raise ValueError("provide exactly one of profile_id or guest_token")

    token_hash = hash_guest_token(guest_token) if guest_token else None

    result = await session.execute(
        select(Cart).where(
            Cart.status.in_([CartStatus.ACTIVE, CartStatus.ABANDONED]),
            Cart.profile_id == profile_id if profile_id else Cart.guest_token_hash == token_hash,
        )
    )
    cart = result.scalar_one_or_none()
    if cart is not None:
        return cart

    cart = Cart(
        profile_id=profile_id,
        guest_token_hash=token_hash,
        status=CartStatus.ACTIVE,
        last_activity_at=datetime.now(UTC),
        # Populate the collection at construction rather than letting the first
        # read fire the `selectin` loader. A cart created in *this* session has
        # never been through a load, so its loader has no greenlet to run on and
        # touching `cart.items` raises `MissingGreenlet`. Initialising it here
        # means a brand-new cart is already "loaded" and needs no query at all.
        items=[],
    )
    session.add(cart)
    try:
        await session.flush()
    except Exception:
        # A concurrent first request can race the partial unique index. The
        # loser simply re-reads: whoever lost the race gets the winner's cart,
        # which is the correct outcome anyway.
        await session.rollback()
        return await get_or_create_cart(
            session, profile_id=profile_id, guest_token=guest_token
        )
    return cart


async def _load_cart_for_read(session: AsyncSession, cart_id: uuid.UUID) -> Cart:
    """Fetch a cart with everything `price_cart` needs, in one pass.

    The eager-load set is explicit rather than relying on relationship defaults,
    because a missing entry here is an N+1 on the hottest customer-facing query
    in the application - the same failure mode the audit found on `/industries`.

    It also has to be explicit for correctness, not only speed: `price_cart`
    re-reads the cart after a mutation, and at that point a relationship whose
    loader has already been spent will not fire again. Naming every hop means no
    caller has to guess.

    Two `selectinload` chains share a path prefix, so they are combined into one
    option rather than restated - `Cart.items` is a single collection and
    `selectinload` applies the whole sub-chain to it.
    """
    result = await session.execute(
        select(Cart)
        .where(Cart.id == cart_id)
        .options(
            selectinload(Cart.items)
            .selectinload(CartItem.variant)
            .options(
                joinedload(ProductVariant.product).options(
                    selectinload(Product.images),
                    joinedload(Product.category),
                ),
                joinedload(ProductVariant.inventory),
            ),
        )
        # Force a real read even though the Cart is already in the identity map.
        # Without this, a cart created moments ago in this session comes back
        # with the empty `items` collection it was constructed with, and the
        # just-added line is invisible: the collection is already "loaded", so
        # `selectinload` has nothing to do. That is not a theoretical case - it
        # is the add-to-cart path, and it silently returned an empty basket.
        .execution_options(populate_existing=True)
    )
    cart = result.scalar_one_or_none()
    if cart is None:
        raise NotFoundError("Your cart could not be found.", code="cart_not_found")
    return cart


# ---------------------------------------------------------------------------
# Pricing
# ---------------------------------------------------------------------------
@dataclass(frozen=True, slots=True)
class CartView:
    """A fully resolved cart. Nothing here came from the request."""

    cart: Cart
    lines: list[PricedLine]
    totals: Totals


def _primary_image_url(variant: ProductVariant) -> str | None:
    """The image to show for a cart line.

    Images belong to the *product*, not the variant, so the product's primary
    image is the answer. That is also the right answer: it is the image the
    customer saw on the card they clicked, so the basket looks like the product
    page they chose from rather than a different render of the same thing.
    """
    product = variant.product
    if product is None:
        return None
    for image in product.images:
        if image.is_primary and image.url:
            return image.url
    for image in product.images:
        if image.url:
            return image.url
    return None


async def price_cart(
    session: AsyncSession,
    cart: Cart,
    *,
    discount_total: int = 0,
    shipping_method: str = "STANDARD",
) -> CartView:
    """Resolve a cart against the catalogue and compute its totals.

    The one function that turns cart rows into numbers. Checkout calls it and
    writes the result to `orders`; the cart page calls it and renders the result.
    Because both go through here, the figure a customer approves and the figure
    they are charged are the same number, produced once.

    The cart is **re-read** rather than trusted as passed in, and that is not
    defensiveness for its own sake. A cart that has just been mutated exists in
    memory as a graph SQLAlchemy has not finished populating: `flush()` writes
    the row but does not populate `item.variant`, and the relationship defaults
    (`lazy="joined"` on the variant's product and inventory) are already-spent
    loaders that will not fire again. Touching them raises `MissingGreenlet`,
    which surfaces as a 500 on a successful add-to-cart.

    So the graph is loaded explicitly here, from the session, with the eager-load
    set that pricing actually needs. One extra bounded query, and no caller has to
    remember to pre-load anything. This is the same lesson as the `/industries`
    N+1 in the QA audit, from the opposite direction: be explicit about loading.
    """
    loaded = await _load_cart_for_read(session, cart.id)
    cart = loaded

    lines: list[PricedLine] = []

    for item in cart.items:
        variant = item.variant
        product = variant.product if variant is not None else None
        if variant is None or product is None:
            # The variant was deleted under us. `cart_items.variant_id` is
            # ON DELETE CASCADE so this should not survive, but a line that
            # cannot be priced must never be silently priced as zero.
            logger.warning("cart_item_orphaned", cart_item_id=str(item.id))
            continue

        available = variant.inventory.available if variant.inventory is not None else 0

        lines.append(
            build_priced_line(
                cart_item_id=item.id,
                quantity=item.quantity,
                variant=variant,
                product=product,
                image_url=_primary_image_url(variant),
                available=available,
            )
        )

    totals = compute_totals(
        lines,
        settings=get_settings(),
        discount_total=discount_total,
        shipping_method=shipping_method,
    )
    return CartView(cart=cart, lines=lines, totals=totals)


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------
async def _load_purchasable_variant(
    session: AsyncSession, variant_id: uuid.UUID
) -> ProductVariant:
    """Load a variant, or explain precisely why it cannot be bought.

    Every branch here is a case a real shopper hits: a product withdrawn from
    sale, a variant discontinued, stock gone. The distinction matters because
    "this is no longer available" and "we are out of stock" lead the customer to
    different next steps.
    """
    result = await session.execute(
        select(ProductVariant)
        .where(ProductVariant.id == variant_id)
        .options(
            joinedload(ProductVariant.product),
            joinedload(ProductVariant.inventory),
        )
    )
    variant = result.scalar_one_or_none()

    if variant is None:
        raise NotFoundError(
            "That product option is not available.", code="variant_not_found"
        )

    if variant.product is None:
        # A variant whose product row is gone. ON DELETE CASCADE should have
        # removed it; treat as not found rather than as a valid line.
        raise NotFoundError(
            "That product is no longer available.", code="product_not_found"
        )

    if variant.status != VariantStatus.ACTIVE:
        raise ValidationError(
            "That product option is no longer available.",
            code="variant_unavailable",
        )

    if variant.product.status != ProductStatus.ACTIVE:
        raise ValidationError(
            "That product is no longer available.", code="product_unavailable",
        )

    return variant


def _check_quantity(quantity: int) -> None:
    if not MIN_QUANTITY <= quantity <= MAX_QUANTITY:
        raise ValidationError(
            f"Choose a quantity between {MIN_QUANTITY} and {MAX_QUANTITY}.",
            code="invalid_quantity",
        )


# ---------------------------------------------------------------------------
# Mutations
# ---------------------------------------------------------------------------
async def add_item(
    session: AsyncSession,
    cart: Cart,
    *,
    variant_id: uuid.UUID,
    quantity: int,
    added_from: str | None = None,
) -> CartItem:
    """Add a variant, or top up the existing line for it.

    Adding the same variant twice **merges** rather than creating a second line.
    Two lines for one variant is a cart the customer cannot reason about, and
    `uq_cart_items_cart_variant` enforces it at the database too.

    The merged quantity is clamped to what stock allows rather than rejected, and
    the caller is told the real number. A customer adding 3 to an existing 2 when
    only 4 are in stock wants the 4; refusing the whole operation would be
    pedantry that loses the sale.
    """
    _check_quantity(quantity)
    variant = await _load_purchasable_variant(session, variant_id)

    available = variant.inventory.available if variant.inventory is not None else 0

    result = await session.execute(
        select(CartItem).where(
            CartItem.cart_id == cart.id, CartItem.variant_id == variant_id
        )
    )
    existing = result.scalar_one_or_none()

    if existing is not None:
        wanted = existing.quantity + quantity
        kept = min(wanted, available) if available > 0 else 0
        if kept <= 0:
            raise InsufficientStockError(
                "This product is no longer available in the requested quantity.",
                code="out_of_stock",
                details={"available": 0},
            )
        if kept < wanted:
            logger.info(
                "cart_merge_clamped_to_stock",
                cart_item_id=str(existing.id),
                wanted=wanted,
                available=available,
            )
        existing.quantity = kept
        await session.flush()
        cart.last_activity_at = datetime.now(UTC)
        return existing

    if available < quantity:
        raise InsufficientStockError(
            "This product is no longer available in the requested quantity.",
            code="insufficient_stock",
            details={"available": available},
        )

    item = CartItem(
        cart_id=cart.id,
        variant_id=variant_id,
        quantity=quantity,
        added_from=(added_from or None) and added_from[:64],
    )
    session.add(item)
    cart.last_activity_at = datetime.now(UTC)
    await session.flush()
    return item


async def update_item(
    session: AsyncSession, cart: Cart, item_id: uuid.UUID, quantity: int
) -> CartItem:
    """Set a line's quantity.

    Scoped by `cart_id` in the WHERE clause, not filtered afterwards. That makes
    cross-cart access impossible by construction: there is no code path in which
    a line belonging to someone else's cart is loaded, so there is nothing to
    leak.
    """
    _check_quantity(quantity)

    result = await session.execute(
        select(CartItem)
        .where(CartItem.id == item_id, CartItem.cart_id == cart.id)
        .options(joinedload(CartItem.variant).joinedload(ProductVariant.inventory))
    )
    item = result.scalar_one_or_none()

    if item is None:
        # 404, not 403: a customer must not be able to probe whether an item id
        # exists in someone else's cart.
        raise NotFoundError("That cart item could not be found.", code="cart_item_not_found")

    available = (
        item.variant.inventory.available if item.variant and item.variant.inventory else 0
    )
    if quantity > available:
        raise InsufficientStockError(
            "This product is no longer available in the requested quantity.",
            code="insufficient_stock",
            details={"available": available},
        )

    item.quantity = quantity
    cart.last_activity_at = datetime.now(UTC)
    await session.flush()
    return item


async def remove_item(session: AsyncSession, cart: Cart, item_id: uuid.UUID) -> None:
    """Delete a line, scoped to this cart."""
    result = await session.execute(
        select(CartItem).where(CartItem.id == item_id, CartItem.cart_id == cart.id)
    )
    item = result.scalar_one_or_none()
    if item is None:
        raise NotFoundError("That cart item could not be found.", code="cart_item_not_found")

    # A cart never holds stock, so removing a line has no inventory effect. That
    # is deliberate: holding stock in a cart would let a customer lock up units
    # they never intend to buy, and stock is only held from payment creation.
    await session.delete(item)
    cart.last_activity_at = datetime.now(UTC)
    await session.flush()


async def clear(session: AsyncSession, cart: Cart) -> None:
    """Empty the cart."""
    await session.execute(delete(CartItem).where(CartItem.cart_id == cart.id))
    cart.last_activity_at = datetime.now(UTC)
    await session.flush()


# ---------------------------------------------------------------------------
# Merge
# ---------------------------------------------------------------------------
async def merge_into_account(
    session: AsyncSession,
    *,
    guest_token: str,
    profile_id: uuid.UUID,
) -> tuple[Cart, list[uuid.UUID], list[tuple[uuid.UUID, str, int, int, str]]]:
    """Fold a guest cart into the customer's account cart on sign-in.

    Order of operations matters:

    1. Load both carts. A guest with no cart simply gets a fresh account cart -
       that is the common case and must not be an error.
    2. For each guest line, add to the account cart **through `add_item`**, not
       by copying rows. Going through the normal path means the merge is subject
       to the same variant, status and stock validation as a live add, and the
       same "merge instead of duplicate" behaviour.
    3. Collect what was merged and what had to be clamped, and **report both**.
       A merge that silently drops units the customer put in a cart is a support
       ticket later; returning the adjustment is the honest version.
    4. Retire the guest cart. It is marked CONVERTED rather than deleted so the
       row's history survives and the token cannot be replayed to re-merge.
    """
    token_hash = hash_guest_token(guest_token)
    guest_result = await session.execute(
        select(Cart).where(
            Cart.guest_token_hash == token_hash,
            Cart.status.in_([CartStatus.ACTIVE, CartStatus.ABANDONED]),
        )
    )
    guest_cart = guest_result.scalar_one_or_none()

    account_cart = await get_or_create_cart(session, profile_id=profile_id)

    if guest_cart is None:
        return account_cart, [], []
    if guest_cart.id == account_cart.id:
        # Already the same cart; nothing to merge and nothing to retire.
        return account_cart, [], []

    merged: list[uuid.UUID] = []
    adjusted: list[tuple[uuid.UUID, str, int, int, str]] = []

    for item in list(guest_cart.items):
        requested = item.quantity
        try:
            result_item = await add_item(
                session,
                account_cart,
                variant_id=item.variant_id,
                quantity=requested,
                added_from="merge",
            )
        except (InsufficientStockError, NotFoundError, ValidationError) as exc:
            # The line cannot be honoured - sold out, withdrawn, or the variant is
            # gone. Skip it and say so; the rest of the cart still merges.
            code = getattr(exc, "code", "unavailable")
            available = await _available_for(session, item.variant_id)
            adjusted.append(
                (
                    item.variant_id,
                    item.variant.sku if item.variant else "",
                    requested,
                    available,
                    str(code),
                )
            )
            logger.info(
                "cart_merge_dropped_line",
                variant_id=str(item.variant_id),
                reason=str(code),
            )
            continue

        merged.append(item.variant_id)
        if result_item.quantity < requested:
            adjusted.append(
                (
                    item.variant_id,
                    result_item.variant.sku if result_item.variant else "",
                    requested,
                    result_item.quantity,
                    "clamped_to_stock",
                )
            )

    guest_cart.status = CartStatus.CONVERTED
    guest_cart.converted_at = datetime.now(UTC)
    account_cart.last_activity_at = datetime.now(UTC)
    await session.flush()

    logger.info(
        "cart_merged",
        profile_id=str(profile_id),
        merged_lines=len(merged),
        adjusted_lines=len(adjusted),
    )
    return account_cart, merged, adjusted


async def _available_for(session: AsyncSession, variant_id: uuid.UUID) -> int:
    return (await inventory_service.available_for_variants(session, [variant_id])).get(
        variant_id, 0
    )


# ---------------------------------------------------------------------------
# Checkout handoff
# ---------------------------------------------------------------------------
async def mark_converted(session: AsyncSession, cart: Cart) -> None:
    """Retire a cart once its order exists.

    A converted cart is not deleted. Keeping it means the order can be traced
    back to the basket that produced it, and it stops being eligible for the
    partial unique index that enforces one live cart per customer.
    """
    cart.status = CartStatus.CONVERTED
    cart.converted_at = datetime.now(UTC)
    await session.flush()


async def touch(session: AsyncSession, cart_id: uuid.UUID) -> None:
    """Record activity, for abandoned-cart recovery.

    A single UPDATE rather than a loaded-then-set, because this runs on every
    cart read and must not drag the whole cart graph in with it.

    ``synchronize_session=False`` is load-bearing. With the default, a bulk
    UPDATE marks the loaded ``Cart`` object's attributes as expired, and the
    next read of ``cart.updated_at`` in the response serialiser fires a
    refresh - which in an async context raises ``MissingGreenlet``, turning a
    successful cart read into a 500. Skipping session synchronisation means the
    in-memory object keeps its values, and the value shown is the last
    *mutation* time, which is what "updated" means to a shopper anyway.
    """
    await session.execute(
        update(Cart)
        .where(Cart.id == cart_id)
        .values(last_activity_at=datetime.now(UTC))
        .execution_options(synchronize_session=False)
    )


async def cart_item_count(session: AsyncSession, cart_id: uuid.UUID) -> int:
    """Units in the cart, for the header badge. One aggregate, no graph."""
    result = await session.execute(
        select(func.coalesce(func.sum(CartItem.quantity), 0)).where(
            CartItem.cart_id == cart_id
        )
    )
    return int(result.scalar_one())


async def find_variant_by_sku(session: AsyncSession, sku: str) -> ProductVariant | None:
    """Reorder helper: find a variant by its human-facing SKU."""
    result = await session.execute(
        select(ProductVariant).where(ProductVariant.sku == sku.strip().upper())
    )
    return result.scalar_one_or_none()


__all__ = [
    "COOKIE_NAME",
    "MAX_QUANTITY",
    "MIN_QUANTITY",
    "CartView",
    "add_item",
    "cart_item_count",
    "clear",
    "effective_unit_price",
    "get_or_create_cart",
    "hash_guest_token",
    "mark_converted",
    "merge_into_account",
    "new_guest_token",
    "price_cart",
    "remove_item",
    "touch",
    "update_item",
]
