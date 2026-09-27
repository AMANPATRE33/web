"""SQLAlchemy model registry.

Importing this package registers every table on ``Base.metadata``, which is
what Alembic autogenerate and ``Base.metadata.create_all`` read. Alembic's
``env.py`` imports it explicitly for that reason.
"""

from __future__ import annotations

from app.db.base import Base
from app.models.catalog import (
    Category,
    Inventory,
    InventoryMovement,
    Product,
    ProductImage,
    ProductTag,
    ProductVariant,
    Tag,
)
from app.models.commerce import (
    Cart,
    CartItem,
    Coupon,
    CouponUsage,
    ShippingMethod,
    Wishlist,
    WishlistItem,
)
from app.models.engagement import (
    AuditLog,
    NewsletterSubscriber,
    ProductRatingSummary,
    Review,
)
from app.models.identity import Address, Profile
from app.models.ops import (
    EmailLog,
    IdempotencyKey,
    IdempotentCounter,
    OutboxEvent,
    StockNotification,
    UserSession,
    WebhookEvent,
)
from app.models.orders import (
    DailySalesFact,
    Order,
    OrderEvent,
    OrderItem,
    Payment,
    Refund,
)

__all__ = [
    "Address",
    "AuditLog",
    "Base",
    "Cart",
    "CartItem",
    "Category",
    "Coupon",
    "CouponUsage",
    "DailySalesFact",
    "EmailLog",
    "IdempotencyKey",
    "IdempotentCounter",
    "Inventory",
    "InventoryMovement",
    "NewsletterSubscriber",
    "Order",
    "OrderEvent",
    "OrderItem",
    "OutboxEvent",
    "Payment",
    "Product",
    "ProductImage",
    "ProductRatingSummary",
    "ProductTag",
    "ProductVariant",
    "Profile",
    "Refund",
    "Review",
    "ShippingMethod",
    "StockNotification",
    "Tag",
    "UserSession",
    "WebhookEvent",
    "Wishlist",
    "WishlistItem",
]
