"""Guest carts, guest orders, reservation ledger, mode-aware order total.

This is the first migration that changes the *shape* of the commerce schema
rather than adding a new feature, and each change below exists for a specific
reason that Phase 2 exposed.

## 1. Anonymous carts

``carts.profile_id`` was ``NOT NULL``, which silently made the cart an
authenticated-only feature. That is fine for a storefront and wrong for a
storefront: a customer must be able to fill a cart before deciding to sign up,
and a surprising share of Indian retail checkouts are guest checkouts.

``carts.guest_token_hash`` holds ``sha256`` of a 256-bit token delivered in an
httpOnly cookie. The *hash* is stored, never the token, so a database dump does
not hand an attacker a set of live carts. The token is looked up by hash, which
keeps the lookup a single indexed equality rather than a scan.

Two partial unique indexes make the invariants structural:

* one live cart per profile (existing, now tolerant of guest rows);
* one live cart per guest token.

PostgreSQL treats NULLs as distinct in a unique index, so a nullable
``profile_id`` cannot collide, and guest carts cannot collide with each other
because their token hashes are unique and non-null.

## 2. Guest orders

Same reasoning as the cart: a guest who completes checkout has an order, and
must be able to see its confirmation and invoice afterwards. ``orders.guest_token_hash``
carries the same scheme. ``profile_id`` moves to ``RESTRICT``-on-delete nullable,
so a profile that never ordered can still be deleted, while a profile *with*
orders is still protected by the foreign key from the other direction.

## 3. Order total is now mode-aware

The original constraint was:

    total = subtotal - discount_total + shipping_total + tax_total

which encodes "tax is **added** to the price". The configured default is
``tax_mode = inclusive`` - GST is **inside** the displayed price, which is how
Indian retail quotes and displays prices. Under that mode tax is a *component of*
the total, not an addition to it, so the old constraint would have rejected
every correct inclusive-mode order (and, worse, invited someone to "fix" it by
zeroing ``tax_total``, destroying the invoice).

The replacement branches on the stored ``tax_inclusive`` flag, so both modes are
constrained by the database and neither can drift:

    inclusive  ->  total = subtotal - discount + shipping
    exclusive  ->  total = subtotal - discount + shipping + tax

``tax_total`` remains the tax *component* in both modes: in inclusive mode the
amount of GST contained in the total, in exclusive mode the amount added to it.
An invoice needs that figure either way.

## 4. orders.tax_split_mode

A GST invoice must show CGST/SGST for an intra-state sale and IGST for an
inter-state one. We store the customer's state as a free-text name, not a state
code, so place-of-supply cannot be derived reliably at render time. Recording
the split that was applied means a historical invoice can be reproduced exactly
even after the configuration changes - the same reasoning that already put
``tax_rate_bps`` on the order.

## 5. inventory_reservations

``docs/ARCHITECTURE.md`` §5 specifies a reservation ledger "so a leaked
reservation is always traceable and reconcilable". It did not exist, so a
reservation released by a failed payment and one lost to a crashed worker were
indistinguishable.

The partial unique index on ``(order_id, variant_id) WHERE status = 'HELD'`` is
the important part: it makes "reserve this line twice" a database error rather
than a double decrement, so a retried payment or replayed webhook cannot
double-release. A released row keeps its history; a new attempt writes a new row.

``expires_at`` is set at creation from ``payment_intent_ttl_seconds`` and swept
by a worker, which is what guarantees ``available < 0`` stays impossible when a
customer abandons a payment window.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0005_guest_carts_reserv"
down_revision: str | None = "0004_freight_shipping"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    # ---------------------------------------------------------------- enums
    # `inventory_reason` already exists from the initial schema; it needs one
    # more value rather than a fresh CREATE TYPE. `reservation_status` is new.
    #
    # `ADD VALUE` is legal inside a transaction from PostgreSQL 12 onward, but
    # the new value cannot be *used* until the transaction commits - so nothing
    # below inserts or defaults to 'EXPIRY'. The column is created against the
    # type, which is fine; it is using a literal that has to wait.
    op.execute("ALTER TYPE inventory_reason ADD VALUE IF NOT EXISTS 'EXPIRY'")

    # ---------------------------------------------------------------- carts
    op.alter_column(
        "carts",
        "profile_id",
        existing_type=postgresql.UUID(as_uuid=True),
        nullable=True,
    )
    op.add_column(
        "carts",
        sa.Column("guest_token_hash", sa.String(length=64), nullable=True),
    )
    op.create_index(
        "uq_carts_one_active_per_guest_token",
        "carts",
        ["guest_token_hash"],
        unique=True,
        postgresql_where=sa.text("guest_token_hash IS NOT NULL AND status IN ('ACTIVE', 'ABANDONED')"),
    )
    # Exactly one owner per cart. Without this, a cart could be reachable both
    # by a profile and by a stolen guest token.
    op.create_check_constraint(
        "carts_exactly_one_owner",
        "carts",
        "(profile_id IS NOT NULL) <> (guest_token_hash IS NOT NULL)",
    )

    # --------------------------------------------------------------- orders
    op.alter_column(
        "orders",
        "profile_id",
        existing_type=postgresql.UUID(as_uuid=True),
        nullable=True,
    )
    op.add_column(
        "orders",
        sa.Column("guest_token_hash", sa.String(length=64), nullable=True),
    )
    op.add_column(
        "orders",
        sa.Column(
            "tax_split_mode",
            sa.String(length=16),
            nullable=False,
            server_default="INTRA_STATE",
        ),
    )
    op.create_check_constraint(
        "orders_exactly_one_owner",
        "orders",
        "(profile_id IS NOT NULL) <> (guest_token_hash IS NOT NULL)",
    )
    op.create_check_constraint(
        "tax_split_mode_known",
        "orders",
        "tax_split_mode IN ('INTRA_STATE', 'INTER_STATE')",
    )

    # The old additive constraint is wrong for GST-inclusive pricing.
    op.drop_constraint("total_consistent", "orders", type_="check")
    op.create_check_constraint(
        "total_consistent",
        "orders",
        # Inclusive: the customer pays the displayed price; GST is inside it.
        "(tax_inclusive AND total = subtotal - discount_total + shipping_total) "
        # Exclusive: GST is added on top of the displayed price.
        "OR (NOT tax_inclusive "
        "AND total = subtotal - discount_total + shipping_total + tax_total)",
    )

    # ----------------------------------------------- inventory reservations
    op.create_table(
        "inventory_reservations",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "variant_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column(
            "order_id",
            postgresql.UUID(as_uuid=True),
            nullable=True,
        ),
        sa.Column("cart_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("quantity", sa.SmallInteger(), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "HELD",
                "COMMITTED",
                "RELEASED",
                "EXPIRED",
                name="reservation_status",
            ),
            nullable=False,
            server_default="HELD",
        ),
        sa.Column(
            "reason",
            # `create_type=False`: the type is created by the ALTER TYPE above,
            # not by this column, and letting SQLAlchemy emit a second
            # CREATE TYPE for an existing type is exactly the failure that
            # happened before this line was added.
            postgresql.ENUM(
                "RESERVATION",
                "RELEASE",
                "SALE",
                "RETURN",
                "ADJUSTMENT",
                "EXPIRY",
                "RESTOCK",
                "DAMAGE",
                name="inventory_reason",
                create_type=False,
            ),
            nullable=False,
            server_default="RESERVATION",
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("released_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("committed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("note", sa.String(length=240), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["variant_id"],
            ["product_variants.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(["order_id"], ["orders.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["cart_id"], ["carts.id"], ondelete="CASCADE"),
        sa.CheckConstraint("quantity > 0", name="reservation_quantity_positive"),
        # A reservation belongs to exactly one holder. A row with neither an
        # order nor a cart is untraceable and must not be creatable.
        sa.CheckConstraint(
            "(order_id IS NOT NULL) OR (cart_id IS NOT NULL)",
            name="reservation_has_holder",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_inventory_reservations"),
    )
    # The structural guarantee that a replayed webhook or a retried payment
    # cannot double-release: one HELD reservation per (order, variant).
    op.create_index(
        "uq_inventory_reservations_held_per_order_variant",
        "inventory_reservations",
        ["order_id", "variant_id"],
        unique=True,
        postgresql_where=sa.text("status = 'HELD'"),
    )
    op.create_index(
        "ix_inventory_reservations_variant_status",
        "inventory_reservations",
        ["variant_id", "status"],
    )
    op.create_index(
        "ix_inventory_reservations_order_id",
        "inventory_reservations",
        ["order_id"],
    )
    # The expiry sweeper's driving query: HELD rows whose deadline has passed.
    op.create_index(
        "ix_inventory_reservations_expiry_sweep",
        "inventory_reservations",
        ["expires_at"],
        postgresql_where=sa.text("status = 'HELD' AND expires_at IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("ix_inventory_reservations_expiry_sweep", table_name="inventory_reservations")
    op.drop_index("ix_inventory_reservations_order_id", table_name="inventory_reservations")
    op.drop_index(
        "ix_inventory_reservations_variant_status", table_name="inventory_reservations"
    )
    op.drop_index(
        "uq_inventory_reservations_held_per_order_variant", table_name="inventory_reservations"
    )
    op.drop_table("inventory_reservations")

    op.drop_constraint("tax_split_mode_known", "orders", type_="check")
    op.drop_constraint("orders_exactly_one_owner", "orders", type_="check")
    op.drop_column("orders", "tax_split_mode")
    op.drop_column("orders", "guest_token_hash")

    op.create_check_constraint(
        "total_consistent",
        "orders",
        "total = subtotal - discount_total + shipping_total + tax_total",
    )
    op.alter_column(
        "orders",
        "profile_id",
        existing_type=postgresql.UUID(as_uuid=True),
        nullable=False,
    )

    op.drop_constraint("carts_exactly_one_owner", "carts", type_="check")
    op.drop_index("uq_carts_one_active_per_guest_token", table_name="carts")
    op.drop_column("carts", "guest_token_hash")
    op.alter_column(
        "carts",
        "profile_id",
        existing_type=postgresql.UUID(as_uuid=True),
        nullable=False,
    )
