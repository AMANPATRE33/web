"""PostgreSQL enum types.

Every enum is created with an explicit name so Alembic can ``ALTER TYPE`` it
predictably. Adding a member is always an additive migration; removing one is
not, which is why no workflow ever *transitions into* a value we might retire.
"""

from __future__ import annotations

from enum import StrEnum


class UserRole(StrEnum):
    """Authorisation role. Always read from ``profiles`` on the server."""

    CUSTOMER = "CUSTOMER"
    ADMIN = "ADMIN"


class ProductStatus(StrEnum):
    DRAFT = "DRAFT"
    ACTIVE = "ACTIVE"
    ARCHIVED = "ARCHIVED"


class VariantStatus(StrEnum):
    ACTIVE = "ACTIVE"
    OUT_OF_STOCK = "OUT_OF_STOCK"
    DISCONTINUED = "DISCONTINUED"


class OrderStatus(StrEnum):
    """Allowed transitions are enforced in ``app.services.orders``."""

    PENDING = "PENDING"
    PAYMENT_PENDING = "PAYMENT_PENDING"
    PAID = "PAID"
    PROCESSING = "PROCESSING"
    SHIPPED = "SHIPPED"
    DELIVERED = "DELIVERED"
    CANCELLED = "CANCELLED"
    REFUNDED = "REFUNDED"


#: Legal forward transitions. Anything else is rejected server-side.
ORDER_TRANSITIONS: dict[OrderStatus, frozenset[OrderStatus]] = {
    OrderStatus.PENDING: frozenset({OrderStatus.PAYMENT_PENDING, OrderStatus.CANCELLED}),
    OrderStatus.PAYMENT_PENDING: frozenset(
        {OrderStatus.PAID, OrderStatus.PENDING, OrderStatus.CANCELLED}
    ),
    OrderStatus.PAID: frozenset(
        {OrderStatus.PROCESSING, OrderStatus.CANCELLED, OrderStatus.REFUNDED}
    ),
    OrderStatus.PROCESSING: frozenset(
        {OrderStatus.SHIPPED, OrderStatus.CANCELLED, OrderStatus.REFUNDED}
    ),
    OrderStatus.SHIPPED: frozenset({OrderStatus.DELIVERED, OrderStatus.REFUNDED}),
    OrderStatus.DELIVERED: frozenset({OrderStatus.REFUNDED}),
    OrderStatus.CANCELLED: frozenset(),
    OrderStatus.REFUNDED: frozenset(),
}

#: Statuses after which no further movement is possible.
TERMINAL_ORDER_STATUSES = frozenset({OrderStatus.CANCELLED, OrderStatus.REFUNDED})


class PaymentStatus(StrEnum):
    CREATED = "CREATED"
    AUTHORIZED = "AUTHORIZED"
    CAPTURED = "CAPTURED"
    FAILED = "FAILED"
    REFUNDED = "REFUNDED"


class PaymentProvider(StrEnum):
    RAZORPAY = "RAZORPAY"


class RefundStatus(StrEnum):
    PENDING = "PENDING"
    PROCESSED = "PROCESSED"
    FAILED = "FAILED"


class CouponType(StrEnum):
    PERCENTAGE = "PERCENTAGE"
    FIXED = "FIXED"


class CartStatus(StrEnum):
    ACTIVE = "ACTIVE"
    CONVERTED = "CONVERTED"
    ABANDONED = "ABANDONED"
    EXPIRED = "EXPIRED"


class AddressType(StrEnum):
    SHIPPING = "SHIPPING"
    BILLING = "BILLING"


class ReviewStatus(StrEnum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


class DiscountSource(StrEnum):
    COUPON = "COUPON"
    MANUAL = "MANUAL"
    LOYALTY = "LOYALTY"


class InventoryReason(StrEnum):
    RESTOCK = "RESTOCK"
    SALE = "SALE"
    RESERVATION = "RESERVATION"
    RELEASE = "RELEASE"
    RETURN = "RETURN"
    ADJUSTMENT = "ADJUSTMENT"
    DAMAGE = "DAMAGE"


class ShippingMethodCode(StrEnum):
    STANDARD = "STANDARD"
    EXPRESS = "EXPRESS"
    #: Large ACP and pylon boards travel differently from an A4 sticker, and
    #: routing them through a parcel courier is how a delivery goes wrong.
    FREIGHT = "FREIGHT"


class SubscriberStatus(StrEnum):
    PENDING = "PENDING"
    ACTIVE = "ACTIVE"
    UNSUBSCRIBED = "UNSUBSCRIBED"
    BOUNCED = "BOUNCED"


class EmailKind(StrEnum):
    WELCOME = "WELCOME"
    EMAIL_VERIFICATION = "EMAIL_VERIFICATION"
    PASSWORD_RESET = "PASSWORD_RESET"  # noqa: S105 - an enum label, not a secret
    ORDER_CONFIRMATION = "ORDER_CONFIRMATION"
    PAYMENT_CONFIRMATION = "PAYMENT_CONFIRMATION"
    PAYMENT_FAILED = "PAYMENT_FAILED"
    SHIPPING_UPDATE = "SHIPPING_UPDATE"
    DELIVERY_CONFIRMATION = "DELIVERY_CONFIRMATION"
    ORDER_CANCELLED = "ORDER_CANCELLED"
    REFUND_ISSUED = "REFUND_ISSUED"
    ABANDONED_CART = "ABANDONED_CART"
    LOW_STOCK_ALERT = "LOW_STOCK_ALERT"
    NEWSLETTER_WELCOME = "NEWSLETTER_WELCOME"


class OutboxStatus(StrEnum):
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    SENT = "SENT"
    FAILED = "FAILED"


class QuoteStatus(StrEnum):
    """Lifecycle of a B2B bulk quote.

    The point of the workflow is that a bulk buyer is *not* forced through
    checkout. They ask, staff quote, and only then does an order exist.
    """

    NEW = "NEW"
    CONTACTED = "CONTACTED"
    QUOTED = "QUOTED"
    CONVERTED = "CONVERTED"
    CLOSED = "CLOSED"


#: Legal forward transitions. Staff may always close; reopening is a
#: deliberate act because it changes someone's queue.
QUOTE_TRANSITIONS: dict[QuoteStatus, frozenset[QuoteStatus]] = {
    QuoteStatus.NEW: frozenset({QuoteStatus.CONTACTED, QuoteStatus.QUOTED, QuoteStatus.CLOSED}),
    QuoteStatus.CONTACTED: frozenset({QuoteStatus.QUOTED, QuoteStatus.CLOSED}),
    QuoteStatus.QUOTED: frozenset(
        {QuoteStatus.CONVERTED, QuoteStatus.CONTACTED, QuoteStatus.CLOSED}
    ),
    QuoteStatus.CONVERTED: frozenset({QuoteStatus.CLOSED}),
    QuoteStatus.CLOSED: frozenset({QuoteStatus.NEW}),
}
