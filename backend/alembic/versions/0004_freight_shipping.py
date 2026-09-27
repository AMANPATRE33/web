"""add FREIGHT shipping method for large boards

Revision ID: 0004_freight_shipping
Revises: 749aef5be6f3
Created: 2026-09-27

ACP and pylon boards do not travel the same way as an A4 sticker: they are
rigid, oversize relative to their weight, and a parcel courier will either
damage them or refuse them. Giving them their own shipping method is a
correctness fix, not a nicety.

``ALTER TYPE ... ADD VALUE`` is additive, so this is safe to run against a live
database with existing orders. Since PostgreSQL 12 the statement is permitted
inside a transaction block; the caveat is that the new value cannot be *used*
until that transaction commits, so nothing in this migration inserts a row
that depends on FREIGHT.
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0004_freight_shipping"
down_revision: str | None = "749aef5be6f3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("ALTER TYPE shipping_method_code ADD VALUE IF NOT EXISTS 'FREIGHT'")
    op.execute("ALTER TYPE order_shipping_method ADD VALUE IF NOT EXISTS 'FREIGHT'")


def downgrade() -> None:
    # PostgreSQL cannot remove a value from an enum. Recreating the type would
    # rewrite every row that uses it, which is a worse outcome than an unused
    # enum value, so this is intentionally a no-op.
    #
    # The consequence: after `alembic downgrade -1`, the schema still *accepts*
    # 'FREIGHT' even though nothing in the application offers it. That is the
    # standard trade-off for an additive enum and is documented rather than
    # hidden - the alternative is a downgrade that raises and blocks the whole
    # rollback chain, which is exactly what a production incident needs working.
    pass
