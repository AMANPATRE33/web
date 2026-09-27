"""Orders, order lines, payments, refunds and the order event log.

Two rules shape this module:

1. **Money on an order is immutable.** ``order_items`` snapshots the unit price,
   title and SKU at purchase time. Changing a catalogue price afterwards must
   never change what a customer was charged, and deleting a product must not
   make a historical order unreadable. The snapshot is the reason a price
   change is safe to deploy mid-day.

2. **Totals are derived, not trusted, and the derivation is stored.** A single
   ``PricingService`` call produces subtotal, discount, shipping, tax and total
   inside the checkout transaction. Those stored values are the record of what
   the customer agreed to pay; the Razorpay amount is then checked against
   ``orders.total`` before capture.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin, enum_column
from app.models.enums import (
    DiscountSource,
    OrderStatus,
    PaymentProvider,
    PaymentStatus,
    RefundStatus,
    ShippingMethodCode,
)

if TYPE_CHECKING:
    from app.models.catalog import Product, ProductVariant
    from app.models.commerce import CouponUsage
    from app.models.identity import Profile


# A native PostgreSQL enum type is created once per type *name*, so the same
# SAEnum instance must be shared by every column that uses it. Declaring two
# separate SAEnum objects with the same name makes SQLAlchemy emit CREATE TYPE
# twice and the second statement fails.
ORDER_STATUS_PG = enum_column(OrderStatus, "order_status", default=OrderStatus.PENDING)
PAYMENT_STATUS_PG = enum_column(PaymentStatus, "payment_status", default=PaymentStatus.CREATED)
SHIPPING_METHOD_PG = enum_column(
    ShippingMethodCode, "order_shipping_method", default=ShippingMethodCode.STANDARD
)


class Order(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "orders"
    __table_args__ = (
        UniqueConstraint("order_number", name="uq_orders_order_number"),
        CheckConstraint("subtotal >= 0", name="subtotal_non_negative"),
        CheckConstraint("discount_total >= 0", name="discount_non_negative"),
        CheckConstraint("shipping_total >= 0", name="shipping_non_negative"),
        CheckConstraint("tax_total >= 0", name="tax_non_negative"),
        CheckConstraint("total >= 0", name="total_non_negative"),
        CheckConstraint(
            "total = subtotal - discount_total + shipping_total + tax_total",
            name="total_consistent",
        ),
        Index("ix_orders_profile_created", "profile_id", "created_at"),
        Index("ix_orders_status_created", "status", "created_at"),
        # Partial index for the fulfilment queue: only live orders, newest first.
        Index(
            "ix_orders_open_queue",
            "created_at",
            postgresql_where=text("status NOT IN ('CANCELLED', 'REFUNDED', 'DELIVERED')"),
        ),
        # Analytics scans aggregate on paid_at, not created_at.
        Index(
            "ix_orders_paid_at",
            "paid_at",
            postgresql_where=text("status NOT IN ('CANCELLED')"),
        ),
        Index("ix_orders_email", "email"),
    )

    #: Human friendly, shown in emails and support. Never sequential.
    order_number: Mapped[str] = mapped_column(String(24), nullable=False)
    profile_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("profiles.id", ondelete="RESTRICT"), nullable=False
    )

    status: Mapped[OrderStatus] = mapped_column(
        ORDER_STATUS_PG,
        nullable=False,
        server_default=OrderStatus.PENDING.value,
    )
    payment_status: Mapped[PaymentStatus] = mapped_column(
        PAYMENT_STATUS_PG,
        nullable=False,
        server_default=PaymentStatus.CREATED.value,
    )
    discount_source: Mapped[DiscountSource | None] = mapped_column(
        enum_column(DiscountSource, "discount_source"),
        nullable=True,
    )

    # --- money, all minor units ---
    subtotal: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    discount_total: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    shipping_total: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    tax_total: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    total: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    refunded_total: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    currency: Mapped[str] = mapped_column(String(3), nullable=False, server_default="INR")

    # --- who ---
    email: Mapped[str] = mapped_column(String(320), nullable=False)
    phone: Mapped[str] = mapped_column(String(24), nullable=False)

    # --- where: denormalised on purpose. A later address-book edit must not
    #     rewrite the destination of a parcel that has already shipped.
    shipping_name: Mapped[str] = mapped_column(String(160), nullable=False)
    shipping_line1: Mapped[str] = mapped_column(String(200), nullable=False)
    shipping_line2: Mapped[str | None] = mapped_column(String(200))
    shipping_landmark: Mapped[str | None] = mapped_column(String(160))
    shipping_city: Mapped[str] = mapped_column(String(96), nullable=False)
    shipping_state: Mapped[str] = mapped_column(String(96), nullable=False)
    shipping_postal_code: Mapped[str] = mapped_column(String(16), nullable=False)
    shipping_country_code: Mapped[str] = mapped_column(
        String(2), nullable=False, server_default="IN"
    )

    billing_name: Mapped[str | None] = mapped_column(String(160))
    billing_line1: Mapped[str | None] = mapped_column(String(200))
    billing_line2: Mapped[str | None] = mapped_column(String(200))
    billing_city: Mapped[str | None] = mapped_column(String(96))
    billing_state: Mapped[str | None] = mapped_column(String(96))
    billing_postal_code: Mapped[str | None] = mapped_column(String(16))
    billing_country_code: Mapped[str | None] = mapped_column(String(2))

    # --- fulfilment ---
    shipping_method: Mapped[ShippingMethodCode] = mapped_column(
        SHIPPING_METHOD_PG,
        nullable=False,
        server_default=ShippingMethodCode.STANDARD.value,
    )
    shipping_carrier: Mapped[str | None] = mapped_column(String(80))
    tracking_number: Mapped[str | None] = mapped_column(String(120))
    tracking_url: Mapped[str | None] = mapped_column(Text)
    estimated_delivery: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # --- lifecycle timestamps ---
    placed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    shipped_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    refunded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cancel_reason: Mapped[str | None] = mapped_column(String(240))

    customer_note: Mapped[str | None] = mapped_column(String(500))
    #: Staff-only notes. Never returned by customer-facing endpoints.
    internal_note: Mapped[str | None] = mapped_column(Text)

    profile: Mapped[Profile] = relationship(back_populates="orders", lazy="joined")
    items: Mapped[list[OrderItem]] = relationship(
        back_populates="order",
        cascade="all, delete-orphan",
        lazy="selectin",
        order_by="OrderItem.position",
    )
    payments: Mapped[list[Payment]] = relationship(
        back_populates="order", lazy="selectin", order_by="Payment.created_at"
    )
    refunds: Mapped[list[Refund]] = relationship(
        back_populates="order", lazy="selectin", order_by="Refund.created_at"
    )
    events: Mapped[list[OrderEvent]] = relationship(
        back_populates="order",
        cascade="all, delete-orphan",
        lazy="noload",
        order_by="OrderEvent.created_at",
    )
    coupon_usage: Mapped[CouponUsage | None] = relationship(
        back_populates="order", uselist=False, lazy="joined"
    )

    @property
    def is_paid(self) -> bool:
        return self.payment_status == PaymentStatus.CAPTURED

    @property
    def can_cancel(self) -> bool:
        return self.status in {OrderStatus.PENDING, OrderStatus.PAYMENT_PENDING, OrderStatus.PAID}

    @property
    def can_refund(self) -> bool:
        return self.payment_status == PaymentStatus.CAPTURED and self.refunded_total < self.total

    def item_count(self) -> int:
        return sum(item.quantity for item in self.items)

    def shipping_address_lines(self) -> list[str]:
        parts = [self.shipping_name, self.shipping_line1]
        if self.shipping_line2:
            parts.append(self.shipping_line2)
        if self.shipping_landmark:
            parts.append(f"near {self.shipping_landmark}")
        parts.append(f"{self.shipping_city}, {self.shipping_state} {self.shipping_postal_code}")
        return parts


class OrderItem(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "order_items"
    __table_args__ = (
        CheckConstraint("quantity > 0", name="quantity_positive"),
        CheckConstraint("unit_price >= 0", name="unit_price_non_negative"),
        Index("ix_order_items_order_id", "order_id"),
        Index("ix_order_items_variant_id", "variant_id"),
        Index("ix_order_items_product_id", "product_id"),
    )

    order_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("orders.id", ondelete="CASCADE"), nullable=False
    )
    product_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("products.id", ondelete="SET NULL"))
    variant_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("product_variants.id", ondelete="SET NULL")
    )

    # --- purchase-time snapshot ---
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    variant_title: Mapped[str] = mapped_column(String(160), nullable=False)
    sku: Mapped[str] = mapped_column(String(64), nullable=False)
    slug: Mapped[str] = mapped_column(String(220), nullable=False)
    image_url: Mapped[str | None] = mapped_column(Text)
    attributes: Mapped[dict[str, object]] = mapped_column(
        JSONB, nullable=False, server_default="{}"
    )

    unit_price: Mapped[int] = mapped_column(Integer, nullable=False)
    compare_at_price: Mapped[int | None] = mapped_column(Integer)
    quantity: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    line_discount: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default="0",
        comment="Per-line share of the coupon discount, for accurate refund maths",
    )
    line_tax: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default="0", comment="Tax attributed to this line"
    )
    total: Mapped[int] = mapped_column(
        Integer, nullable=False, comment="unit_price * quantity - line_discount + line_tax"
    )
    refunded_quantity: Mapped[int] = mapped_column(SmallInteger, nullable=False, server_default="0")
    position: Mapped[int] = mapped_column(SmallInteger, nullable=False, server_default="0")

    order: Mapped[Order] = relationship(back_populates="items", lazy="joined")
    product: Mapped[Product | None] = relationship(lazy="joined")
    variant: Mapped[ProductVariant | None] = relationship(
        back_populates="order_items", lazy="joined"
    )


class OrderEvent(UUIDPrimaryKeyMixin, Base):
    """Append-only order timeline, shown to the customer and to staff."""

    __tablename__ = "order_events"
    __table_args__ = (Index("ix_order_events_order_created", "order_id", "created_at"),)

    order_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("orders.id", ondelete="CASCADE"), nullable=False
    )
    from_status: Mapped[OrderStatus | None] = mapped_column(ORDER_STATUS_PG, nullable=True)
    to_status: Mapped[OrderStatus] = mapped_column(ORDER_STATUS_PG, nullable=False)
    note: Mapped[str | None] = mapped_column(String(400))
    #: NULL for system transitions, set for staff actions.
    actor_profile_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("profiles.id", ondelete="SET NULL")
    )
    is_customer_visible: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="true"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()"), nullable=False
    )

    order: Mapped[Order] = relationship(back_populates="events", lazy="joined")


class Payment(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "payments"
    __table_args__ = (
        UniqueConstraint("razorpay_order_id", name="uq_payments_razorpay_order_id"),
        UniqueConstraint("razorpay_payment_id", name="uq_payments_razorpay_payment_id"),
        CheckConstraint("amount > 0", name="amount_positive"),
        Index("ix_payments_order_id", "order_id"),
        Index("ix_payments_status", "status"),
        Index("ix_payments_created_at", "created_at"),
    )

    order_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("orders.id", ondelete="CASCADE"), nullable=False
    )
    provider: Mapped[PaymentProvider] = mapped_column(
        enum_column(PaymentProvider, "payment_provider", default=PaymentProvider.RAZORPAY),
        nullable=False,
        server_default=PaymentProvider.RAZORPAY.value,
    )
    status: Mapped[PaymentStatus] = mapped_column(
        enum_column(PaymentStatus, "payment_status", default=PaymentStatus.CREATED),
        nullable=False,
        server_default=PaymentStatus.CREATED.value,
    )

    amount: Mapped[int] = mapped_column(Integer, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, server_default="INR")

    razorpay_order_id: Mapped[str | None] = mapped_column(String(64))
    razorpay_payment_id: Mapped[str | None] = mapped_column(String(64))
    razorpay_signature: Mapped[str | None] = mapped_column(String(128))
    method: Mapped[str | None] = mapped_column(String(48))
    bank: Mapped[str | None] = mapped_column(String(96))
    #: Gateway response, stored verbatim for dispute resolution.
    gateway_payload: Mapped[dict[str, object] | None] = mapped_column(JSONB)
    failure_code: Mapped[str | None] = mapped_column(String(96))
    failure_reason: Mapped[str | None] = mapped_column(String(400))
    captured_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    order: Mapped[Order] = relationship(back_populates="payments", lazy="joined")


class Refund(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "refunds"
    __table_args__ = (
        UniqueConstraint("razorpay_refund_id", name="uq_refunds_razorpay_refund_id"),
        CheckConstraint("amount > 0", name="amount_positive"),
        Index("ix_refunds_order_id", "order_id"),
    )

    order_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("orders.id", ondelete="CASCADE"), nullable=False
    )
    payment_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("payments.id", ondelete="RESTRICT"), nullable=False
    )
    amount: Mapped[int] = mapped_column(Integer, nullable=False)
    reason: Mapped[str] = mapped_column(String(240), nullable=False)
    status: Mapped[RefundStatus] = mapped_column(
        enum_column(RefundStatus, "refund_status", default=RefundStatus.PENDING),
        nullable=False,
        server_default=RefundStatus.PENDING.value,
    )
    razorpay_refund_id: Mapped[str | None] = mapped_column(String(64))
    #: True when stock is intentionally NOT returned to sellable inventory.
    restock: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")
    requested_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("profiles.id", ondelete="SET NULL")
    )
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    failure_reason: Mapped[str | None] = mapped_column(String(400))

    order: Mapped[Order] = relationship(back_populates="refunds", lazy="joined")


class DailySalesFact(Base):
    """Pre-aggregated revenue per day, produced by the ``aggregate_sales_daily``
    job. The admin dashboard reads this instead of scanning ``orders``."""

    __tablename__ = "analytics_daily"
    __table_args__ = (UniqueConstraint("day", name="uq_analytics_daily_day"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    day: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    orders_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    items_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    gross_revenue: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    discount_total: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    tax_total: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    shipping_total: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    refunded_total: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    new_customers: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()"), nullable=False
    )

    @property
    def net_revenue(self) -> int:
        return self.gross_revenue - self.refunded_total

    @property
    def average_order_value(self) -> Decimal:
        if not self.orders_count:
            return Decimal("0.00")
        return (Decimal(self.net_revenue) / Decimal(self.orders_count)).quantize(Decimal("0.01"))
