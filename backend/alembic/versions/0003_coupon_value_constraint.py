"""coupon value constraint is conditional on coupon type

Revision ID: 0003_coupon_value_constraint
Revises: 0002_triggers
Created: 2026-09-27

Found by seeding: the original constraint was a single range,

    CHECK (value > 0 AND value <= 10000)

which is only correct for ``PERCENTAGE`` coupons, where ``value`` is basis
points. A ``FIXED`` coupon stores minor units, so "Rs. 500 off" is ``50000`` -
comfortably outside a 10000 bound - and the seed data could not be inserted.

Both bounds are now expressed in one conditional constraint rather than two
overlapping ones, so a row can never satisfy one while violating the other.
The old constraint is dropped rather than left in place: keeping a
``value <= 10000`` check for FIXED coupons would reintroduce the same bug.

This is an additive, reversible schema change; no data is rewritten.
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0003_coupon_value_constraint"
down_revision: str | None = "0002_triggers"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("ALTER TABLE coupons DROP CONSTRAINT IF EXISTS ck_coupons_percentage_basis_points_in_range")

    op.execute(
        """
        ALTER TABLE coupons
        ADD CONSTRAINT ck_coupons_coupon_value_in_range_for_type
        CHECK (
            (coupon_type = 'PERCENTAGE' AND value > 0 AND value <= 10000)
            OR (coupon_type = 'FIXED' AND value > 0)
        )
        """
    )
    op.execute(
        """
        ALTER TABLE coupons
        ADD CONSTRAINT ck_coupons_max_discount_positive
        CHECK (max_discount_amount IS NULL OR max_discount_amount > 0)
        """
    )
    op.execute(
        """
        ALTER TABLE coupons
        ADD CONSTRAINT ck_coupons_min_order_amount_non_negative
        CHECK (min_order_amount >= 0)
        """
    )


def downgrade() -> None:
    op.execute("ALTER TABLE coupons DROP CONSTRAINT IF EXISTS ck_coupons_min_order_amount_non_negative")
    op.execute("ALTER TABLE coupons DROP CONSTRAINT IF EXISTS ck_coupons_max_discount_positive")
    op.execute("ALTER TABLE coupons DROP CONSTRAINT IF EXISTS ck_coupons_coupon_value_in_range_for_type")

    # The original constraint is restored, which means any FIXED coupon worth
    # more than Rs. 100 will not fit afterwards. That is a faithful restoration of
    # the previous behaviour, and is why this migration is documented as the
    # point at which that limit was lifted.
    op.execute(
        """
        ALTER TABLE coupons
        ADD CONSTRAINT ck_coupons_percentage_basis_points_in_range
        CHECK (value > 0 AND value <= 10000)
        """
    )
