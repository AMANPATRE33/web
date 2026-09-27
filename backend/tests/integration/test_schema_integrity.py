"""Database-level integrity tests.

These assert the guarantees that live *in the schema*, not in Python. If one of
these fails, an application bug can corrupt data even though every service
function is correct - which is exactly the class of bug that is expensive to
discover in production.
"""

from __future__ import annotations

import uuid

import pytest
from app.models.catalog import Category, Inventory, Product, ProductVariant
from app.models.enums import PaymentStatus, ProductStatus, VariantStatus
from app.models.orders import Order
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError, IntegrityError

pytestmark = pytest.mark.integration


async def _make_category(session, **kwargs) -> Category:
    category = Category(
        name=kwargs.pop("name", "Headphones"),
        slug=kwargs.pop("slug", f"cat-{uuid.uuid4().hex[:8]}"),
        **kwargs,
    )
    session.add(category)
    await session.flush()
    return category


async def _make_product(session, category: Category, **kwargs) -> Product:
    product = Product(
        title=kwargs.pop("title", "Aurelius One"),
        slug=kwargs.pop("slug", f"p-{uuid.uuid4().hex[:8]}"),
        description=kwargs.pop("description", "Over-ear wireless headphones."),
        short_description=kwargs.pop("short_description", "Wireless over-ear"),
        sku=kwargs.pop("sku", f"SKU-{uuid.uuid4().hex[:8]}"),
        category_id=category.id,
        base_price=kwargs.pop("base_price", 2499000),
        compare_at_price=kwargs.pop("compare_at_price", None),
        status=kwargs.pop("status", ProductStatus.ACTIVE),
        **kwargs,
    )
    session.add(product)
    await session.flush()
    return product


# ---------------------------------------------------------------------------
# generated columns and triggers
# ---------------------------------------------------------------------------
async def test_inventory_available_is_generated(session) -> None:
    """``available`` must be derived, never written."""
    category = await _make_category(session)
    product = await _make_product(session, category)
    variant = ProductVariant(
        product_id=product.id,
        sku=f"V-{uuid.uuid4().hex[:8]}",
        title="One",
        attributes={"Colour": "Black"},
    )
    session.add(variant)
    await session.flush()
    session.add(Inventory(variant_id=variant.id, quantity=10, reserved=3))
    await session.commit()

    # Read the row directly rather than through the relationship: touching
    # `variant.inventory` after a commit would trigger a lazy load outside the
    # async greenlet context (MissingGreenlet).
    result = await session.execute(
        text("SELECT quantity, reserved, available FROM inventory WHERE variant_id = :v"),
        {"v": variant.id},
    )
    quantity, reserved, available = result.one()
    assert (quantity, reserved, available) == (10, 3, 7)


async def test_inventory_available_cannot_be_written(session) -> None:
    """A direct write to the generated column must be rejected."""
    category = await _make_category(session)
    product = await _make_product(session, category)
    variant = ProductVariant(product_id=product.id, sku=f"V-{uuid.uuid4().hex[:8]}", title="One")
    session.add(variant)
    await session.flush()
    session.add(Inventory(variant_id=variant.id, quantity=4, reserved=1))
    await session.commit()

    with pytest.raises(DBAPIError, match="can only be updated to DEFAULT"):
        await session.execute(
            text("UPDATE inventory SET available = 99 WHERE variant_id = :v"),
            {"v": variant.id},
        )
        await session.commit()


async def test_reserved_cannot_exceed_quantity(session) -> None:
    category = await _make_category(session)
    product = await _make_product(session, category)
    variant = ProductVariant(product_id=product.id, sku=f"V-{uuid.uuid4().hex[:8]}", title="One")
    session.add(variant)
    await session.flush()
    session.add(Inventory(variant_id=variant.id, quantity=5, reserved=0))
    await session.commit()

    with pytest.raises(IntegrityError, match="reserved_not_over_quantity"):
        await session.execute(
            text("UPDATE inventory SET reserved = 6 WHERE variant_id = :v"),
            {"v": variant.id},
        )
        await session.commit()


async def test_price_min_maintained_by_trigger(session) -> None:
    """Adding a cheaper variant must lower the advertised floor immediately."""
    category = await _make_category(session)
    product = await _make_product(session, category, base_price=500000)
    session.commit()

    variant = ProductVariant(
        product_id=product.id,
        sku=f"V-{uuid.uuid4().hex[:8]}",
        title="One",
        price_override=400000,
    )
    session.add(variant)
    await session.commit()
    await session.refresh(product)
    assert product.price_min == 400000
    assert product.price_max == 400000

    # Removing the only purchasable variant leaves nothing to advertise, so the
    # floor is NULL rather than silently falling back to the base price.
    # NOTE: AsyncSession.delete is a coroutine in SQLAlchemy >= 2.1 and must be
    # awaited. Calling it synchronously marks nothing and the flush is a no-op.
    await session.delete(variant)
    await session.commit()
    await session.refresh(product)
    assert product.price_min is None


async def test_discontinued_variant_excluded_from_price_range(session) -> None:
    """A cheaper discontinued variant must stop setting the advertised floor."""
    category = await _make_category(session)
    product = await _make_product(session, category, base_price=500000)
    session.commit()

    expensive = ProductVariant(
        product_id=product.id,
        sku=f"V-{uuid.uuid4().hex[:8]}",
        title="Standard",
    )
    cheap = ProductVariant(
        product_id=product.id,
        sku=f"V-{uuid.uuid4().hex[:8]}",
        title="Discounted",
        price_override=100000,
    )
    session.add_all([expensive, cheap])
    await session.commit()
    await session.refresh(product)
    assert product.price_min == 100000

    cheap.status = VariantStatus.DISCONTINUED
    await session.commit()
    await session.refresh(product)
    assert product.price_min == 500000


async def test_variant_price_override_removed_restores_base_price(session) -> None:
    category = await _make_category(session)
    product = await _make_product(session, category, base_price=500000)
    session.commit()

    variant = ProductVariant(
        product_id=product.id,
        sku=f"V-{uuid.uuid4().hex[:8]}",
        title="One",
        price_override=420000,
    )
    session.add(variant)
    await session.commit()
    await session.refresh(product)
    assert product.price_min == 420000

    # Clearing the override makes the variant inherit products.base_price.
    variant.price_override = None
    await session.commit()
    await session.refresh(product)
    assert product.price_min == 500000


async def test_search_vector_populated_by_trigger(session) -> None:
    category = await _make_category(session)
    product = await _make_product(
        session,
        category,
        title="Noise cancelling over-ear headphones",
        brand="Aurelius",
    )
    await session.commit()
    await session.refresh(product)
    assert product.search_vector is not None
    # to_tsvector('english', …) stems, so "noise" is stored as "nois". Assert on
    # the stemmed form and on a weight letter to prove this is the trigger's
    # weighted output rather than an unweighted default.
    assert "nois" in str(product.search_vector)
    assert "aurelius" in str(product.search_vector)
    assert "3A" in str(product.search_vector) or "6A" in str(product.search_vector)


async def test_search_vector_is_gin_indexed(session) -> None:
    """Full text search must use the index, not a sequential scan."""
    result = await session.execute(
        text(
            """
            SELECT indexdef FROM pg_indexes
            WHERE tablename = 'products' AND indexname = 'ix_products_search'
            """
        )
    )
    indexdef = result.scalar_one().lower()
    assert "using gin" in indexdef


async def test_category_path_maintained_and_cycles_refused(session) -> None:
    root = await _make_category(session, name="Audio", slug=f"root-{uuid.uuid4().hex[:8]}")
    child = await _make_category(
        session, name="Headphones", slug=f"child-{uuid.uuid4().hex[:8]}", parent_id=root.id
    )
    grandchild = await _make_category(
        session, name="Over-ear", slug=f"gc-{uuid.uuid4().hex[:8]}", parent_id=child.id
    )
    await session.commit()

    assert root.path == ""
    assert child.path == str(root.id)
    assert grandchild.path == f"{root.id},{child.id}"

    # Making an ancestor its own descendant must fail at the database level.
    with pytest.raises(DBAPIError, match="descendant of itself"):
        await session.execute(
            text("UPDATE categories SET parent_id = :child WHERE id = :root"),
            {"child": child.id, "root": root.id},
        )
        await session.rollback()


async def test_updated_at_trigger_fires_on_raw_sql(session) -> None:
    """A raw UPDATE (no ORM) must still bump updated_at."""
    category = await _make_category(session)
    await session.commit()

    before = category.updated_at
    await session.execute(
        text("UPDATE categories SET name = 'Renamed' WHERE id = :id"), {"id": category.id}
    )
    await session.commit()

    await session.refresh(category)
    assert category.updated_at > before
    assert category.name == "Renamed"


# ---------------------------------------------------------------------------
# partial unique indexes
# ---------------------------------------------------------------------------
async def test_only_one_primary_image_per_product(session) -> None:
    from app.models.catalog import ProductImage

    category = await _make_category(session)
    product = await _make_product(session, category)
    session.add(ProductImage(product_id=product.id, url="a.jpg", is_primary=True))
    await session.flush()
    session.add(ProductImage(product_id=product.id, url="b.jpg", is_primary=True))
    with pytest.raises(IntegrityError, match="uq_product_images_one_primary"):
        await session.commit()


async def test_only_one_default_address_per_profile(session) -> None:
    from app.models.identity import Address, Profile

    profile = Profile(id=uuid.uuid4(), email=f"dup-{uuid.uuid4().hex[:8]}@example.com")
    session.add(profile)
    await session.flush()
    base = {
        "profile_id": profile.id,
        "full_name": "Test",
        "phone": "9999999999",
        "line1": "1 Test Street",
        "city": "Pune",
        "state": "Maharashtra",
        "postal_code": "411001",
    }
    session.add(Address(**base, is_default=True))
    await session.flush()
    session.add(Address(**{**base, "line1": "2 Test Street"}, is_default=True))
    with pytest.raises(IntegrityError, match="uq_addresses_one_default_per_profile"):
        await session.commit()


# ---------------------------------------------------------------------------
# order money invariants
# ---------------------------------------------------------------------------
async def test_order_total_consistency_is_enforced(session, make_profile) -> None:
    """The database itself must reject an order whose totals do not add up.

    Both tax modes are covered, because the constraint branches on
    ``tax_inclusive``. Testing only one is how the previous version of this test
    came to pass for the wrong reason: the old constraint assumed tax was always
    *added*, so once inclusive pricing became possible the same bad total was
    still rejected - just by a different clause of the formula.

    Each assertion runs inside a SAVEPOINT. A failed flush otherwise poisons the
    whole session with ``PendingRollbackError``, and the next assertion would
    fail for the wrong reason - or, worse, pass without ever reaching the CHECK.
    """
    base = dict(
        email="x@example.com",
        phone="9999999999",
        shipping_name="X",
        shipping_line1="1 St",
        shipping_city="Pune",
        shipping_state="MH",
        shipping_postal_code="411001",
        subtotal=100000,
        discount_total=10000,
        shipping_total=5000,
        tax_total=18000,
    )

    async def expect_rejected(constraint: str, **overrides) -> None:
        savepoint = await session.begin_nested()
        session.add(
            Order(
                **base,
                order_number=f"TEST-{uuid.uuid4().hex[:8]}",
                profile_id=uuid.uuid4(),
                **overrides,
            )
        )
        with pytest.raises(IntegrityError, match=constraint):
            await session.flush()
        await savepoint.rollback()

    async def expect_accepted(**overrides) -> Order:
        # A real profile row: the accepted case must satisfy the foreign key too,
        # or it would fail for a different reason than the one under test.
        profile = await make_profile()
        savepoint = await session.begin_nested()
        order = Order(
            **base,
            order_number=f"TEST-{uuid.uuid4().hex[:8]}",
            profile_id=profile.id,
            **overrides,
        )
        session.add(order)
        await session.flush()
        await savepoint.commit()
        return order

    # GST-inclusive: tax is inside `subtotal`, so it must NOT be added again.
    # Correct total is 100000 - 10000 + 5000 = 95000; 113000 double-counts tax.
    await expect_rejected("total_consistent", tax_inclusive=True, total=113000)

    # GST-exclusive: tax is added on top.
    # Correct total is 100000 - 10000 + 5000 + 18000 = 113000; 95000 drops tax.
    await expect_rejected("total_consistent", tax_inclusive=False, total=95000)

    # And the correct figure in each mode must be accepted, so this test cannot
    # pass simply by rejecting everything.
    inclusive = await expect_accepted(tax_inclusive=True, total=95000)
    assert inclusive.total == inclusive.subtotal - inclusive.discount_total + (
        inclusive.shipping_total
    )
    exclusive = await expect_accepted(tax_inclusive=False, total=113000)
    assert exclusive.total == (
        exclusive.subtotal
        - exclusive.discount_total
        + exclusive.shipping_total
        + exclusive.tax_total
    )


async def test_order_needs_exactly_one_owner(session) -> None:
    """A cart or order reachable by both a profile and a guest token is a
    cross-account read, so the database refuses to represent that state."""
    base = dict(
        email="x@example.com",
        phone="9",
        shipping_name="X",
        shipping_line1="1 St",
        shipping_city="Pune",
        shipping_state="MH",
        shipping_postal_code="411001",
        subtotal=0,
        discount_total=0,
        shipping_total=0,
        tax_total=0,
        total=0,
    )

    async def attempt(**kwargs):
        savepoint = await session.begin_nested()
        session.add(
            Order(**base, order_number=f"TEST-{uuid.uuid4().hex[:8]}", **kwargs)
        )
        try:
            await session.flush()
        finally:
            await savepoint.rollback()

    # Neither owner.
    with pytest.raises(IntegrityError, match="orders_exactly_one_owner"):
        await attempt()

    # Both owners.
    with pytest.raises(IntegrityError, match="orders_exactly_one_owner"):
        await attempt(profile_id=uuid.uuid4(), guest_token_hash="a" * 64)

    # Guest only is legitimate: guest checkout has to work.
    savepoint = await session.begin_nested()
    session.add(
        Order(
            **base,
            order_number=f"TEST-{uuid.uuid4().hex[:8]}",
            guest_token_hash="b" * 64,
        )
    )
    await session.flush()
    await savepoint.commit()


async def test_tax_split_mode_must_be_known(session) -> None:
    """An invoice's CGST/IGST split is a legal statement, so the value is
    constrained rather than accepted as free text."""
    savepoint = await session.begin_nested()
    session.add(
        Order(
            order_number=f"TEST-{uuid.uuid4().hex[:8]}",
            profile_id=uuid.uuid4(),
            email="x@example.com",
            phone="9",
            shipping_name="X",
            shipping_line1="1 St",
            shipping_city="Pune",
            shipping_state="MH",
            shipping_postal_code="411001",
            subtotal=0,
            discount_total=0,
            shipping_total=0,
            tax_total=0,
            total=0,
            tax_split_mode="MAYBE",
        )
    )
    with pytest.raises(IntegrityError, match="tax_split_mode_known"):
        await session.flush()
    await savepoint.rollback()

async def test_order_profile_fk_protects_history(session) -> None:
    session.add(
        Order(
            order_number=f"TEST-{uuid.uuid4().hex[:8]}",
            profile_id=uuid.uuid4(),
            email="x@example.com",
            phone="9",
            shipping_name="X",
            shipping_line1="1 St",
            shipping_city="Pune",
            shipping_state="MH",
            shipping_postal_code="411001",
            subtotal=0,
            discount_total=0,
            shipping_total=0,
            tax_total=0,
            total=0,
        )
    )
    with pytest.raises(IntegrityError):
        await session.commit()


async def test_payment_amount_must_be_positive(session) -> None:
    from app.models.orders import Payment

    session.add(
        Payment(
            order_id=uuid.uuid4(),
            status=PaymentStatus.CREATED,
            amount=0,
        )
    )
    with pytest.raises(IntegrityError, match="amount_positive"):
        await session.commit()


# ---------------------------------------------------------------------------
# enum integrity
# ---------------------------------------------------------------------------
async def test_order_status_enum_rejects_unknown_value(session) -> None:
    category_ok = await session.execute(text("SELECT 'PAID'::order_status"))
    assert category_ok.scalar_one() == "PAID"
    with pytest.raises(DBAPIError):
        await session.execute(text("SELECT 'TOTALLY_MADE_UP'::order_status"))


async def test_partial_index_only_covers_live_orders(session) -> None:
    """A cancelled order must not block a new live cart for the same user."""
    result = await session.execute(
        text(
            """
            SELECT indexdef FROM pg_indexes
            WHERE indexname = 'uq_carts_one_active_per_user'
            """
        )
    )
    indexdef = result.scalar_one()
    assert "WHERE" in indexdef
    assert "ACTIVE" in indexdef
