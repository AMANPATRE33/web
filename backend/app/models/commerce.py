"""Cart, wishlist, coupons and shipping.

Carts store **no prices**. A cart row holds a variant id and a quantity; every
figure shown to a customer is recomputed from the catalogue on read. This is
deliberate: a cached total is either stale (price changed, customer notices and
questions it) or trusted (tamperable). Recomputing is cheap because the query
joins a handful of indexed tables, and it means there is exactly one place in
the codebase where a cart total is produced - the pricing service.
"""

from __future__ import annotations

import uuid
from datetime import datetime
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
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin, enum_column
from app.models.catalog import ProductVariant
from app.models.enums import CartStatus, CouponType, ShippingMethodCode

if TYPE_CHECKING:
    from app.models.identity import Profile
    from app.models.orders import Order


class Cart(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "carts"
    __table_args__ = (
        # A user has at most one live cart. Historic carts become CONVERTED or
        # EXPIRED and no longer conflict with this constraint.
        Index(
            "uq_carts_one_active_per_user",
            "profile_id",
            unique=True,
            postgresql_where=text("status IN ('ACTIVE', 'ABANDONED')"),
        ),
        Index("ix_carts_status_updated_at", "status", "updated_at"),
    )

    profile_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("profiles.id", ondelete="CASCADE"), nullable=False
    )
    status: Mapped[CartStatus] = mapped_column(
        enum_column(CartStatus, "cart_status", default=CartStatus.ACTIVE),
        nullable=False,
        server_default=CartStatus.ACTIVE.value,
    )
    #: Marketing attribution. Never used for pricing.
    coupon_code_snapshot: Mapped[str | None] = mapped_column(String(48))
    last_activity_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    converted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    #: Set when the abandoned-cart job picks this cart up.
    recovery_sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    recovery_token: Mapped[str | None] = mapped_column(String(64))

    profile: Mapped[Profile] = relationship(back_populates="cart", lazy="joined")
    items: Mapped[list[CartItem]] = relationship(
        back_populates="cart",
        cascade="all, delete-orphan",
        lazy="selectin",
        order_by="CartItem.created_at",
    )


class CartItem(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "cart_items"
    __table_args__ = (
        # Adding the same variant twice merges quantity instead of duplicating.
        UniqueConstraint("cart_id", "variant_id", name="uq_cart_items_cart_variant"),
        CheckConstraint("quantity > 0", name="quantity_positive"),
        CheckConstraint("quantity <= 99", name="quantity_max_99"),
        Index("ix_cart_items_cart_id", "cart_id"),
        Index("ix_cart_items_variant_id", "variant_id"),
    )

    cart_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("carts.id", ondelete="CASCADE"), nullable=False
    )
    variant_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("product_variants.id", ondelete="CASCADE"), nullable=False
    )
    quantity: Mapped[int] = mapped_column(SmallInteger, nullable=False, server_default="1")
    #: Non-price client hints used to explain cart contents in support tickets.
    added_from: Mapped[str | None] = mapped_column(String(64))

    cart: Mapped[Cart] = relationship(back_populates="items", lazy="joined")
    variant: Mapped[ProductVariant] = relationship(back_populates="cart_items", lazy="joined")


class Wishlist(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "wishlists"
    __table_args__ = (UniqueConstraint("profile_id", name="uq_wishlists_profile_id"),)

    profile_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("profiles.id", ondelete="CASCADE"), nullable=False
    )

    profile: Mapped[Profile] = relationship(back_populates="wishlist", lazy="joined")
    items: Mapped[list[WishlistItem]] = relationship(
        back_populates="wishlist", cascade="all, delete-orphan", lazy="selectin"
    )


class WishlistItem(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "wishlist_items"
    __table_args__ = (
        UniqueConstraint("wishlist_id", "variant_id", name="uq_wishlist_items_wishlist_variant"),
        Index("ix_wishlist_items_wishlist_id", "wishlist_id"),
    )

    wishlist_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("wishlists.id", ondelete="CASCADE"), nullable=False
    )
    #: Wishlisting is at variant level so colour/size choices are preserved.
    variant_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("product_variants.id", ondelete="CASCADE"), nullable=False
    )
    #: Notified when this variant returns to stock.
    notify_on_restock: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    notified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    wishlist: Mapped[Wishlist] = relationship(back_populates="items", lazy="joined")
    variant: Mapped[ProductVariant] = relationship(back_populates="wishlist_items", lazy="joined")


class ShippingMethod(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Configurable shipping options presented at checkout."""

    __tablename__ = "shipping_methods"
    __table_args__ = (
        UniqueConstraint("code", name="uq_shipping_methods_code"),
        CheckConstraint("price >= 0", name="price_non_negative"),
    )

    code: Mapped[ShippingMethodCode] = mapped_column(
        enum_column(ShippingMethodCode, "shipping_method_code"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(80), nullable=False)
    description: Mapped[str | None] = mapped_column(String(200))
    #: Minor units.
    price: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    #: NULL disables the free-shipping threshold.
    free_above: Mapped[int | None] = mapped_column(Integer)
    estimated_days_min: Mapped[int] = mapped_column(
        SmallInteger, nullable=False, server_default="3"
    )
    estimated_days_max: Mapped[int] = mapped_column(
        SmallInteger, nullable=False, server_default="5"
    )
    #: Multiplier applied to shipping for express handling.
    handling_fee: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")
    position: Mapped[int] = mapped_column(SmallInteger, nullable=False, server_default="0")


class Coupon(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Discount rules. Always evaluated server-side by ``CouponService``."""

    __tablename__ = "coupons"
    __table_args__ = (
        UniqueConstraint("code", name="uq_coupons_code"),
        CheckConstraint("value > 0 AND value <= 10000", name="percentage_basis_points_in_range"),
        # The two coupon types store `value` in different units, so the bound
        # has to be conditional rather than a single range: PERCENTAGE is basis
        # points (1..10000 == 0.01%..100%), FIXED is minor units, which is
        # routinely far above 10000. A single `value <= 10000` check rejects a
        # perfectly ordinary "Rs. 500 off" coupon - which is exactly what the
        # seed data exposed.
        CheckConstraint(
            "(coupon_type = 'PERCENTAGE' AND value > 0 AND value <= 10000) "
            "OR (coupon_type = 'FIXED' AND value > 0)",
            name="coupon_value_in_range_for_type",
        ),
        CheckConstraint(
            "max_discount_amount IS NULL OR max_discount_amount > 0",
            name="max_discount_positive",
        ),
        CheckConstraint("min_order_amount >= 0", name="min_order_amount_non_negative"),
        CheckConstraint(
            "usage_limit IS NULL OR usage_count < usage_limit", name="usage_under_limit"
        ),
        CheckConstraint(
            "per_user_limit IS NULL OR per_user_limit > 0", name="per_user_limit_positive"
        ),
        Index("ix_coupons_is_active_expires_at", "is_active", "expires_at"),
    )

    code: Mapped[str] = mapped_column(String(48), nullable=False)
    description: Mapped[str | None] = mapped_column(String(240))
    coupon_type: Mapped[CouponType] = mapped_column(
        enum_column(CouponType, "coupon_type"), nullable=False
    )
    #: PERCENTAGE: basis points (1500 = 15.00%). FIXED: minor units (paise).
    value: Mapped[int] = mapped_column(Integer, nullable=False)
    #: Caps a percentage discount. NULL means uncapped.
    max_discount_amount: Mapped[int | None] = mapped_column(Integer)
    min_order_amount: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")

    starts_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    usage_limit: Mapped[int | None] = mapped_column(Integer)
    usage_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    per_user_limit: Mapped[int | None] = mapped_column(Integer)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")

    #: Optional scoping. Empty/absent means "applies to everything".
    category_ids: Mapped[list[str] | None] = mapped_column(JSONB)
    product_ids: Mapped[list[str] | None] = mapped_column(JSONB)
    #: Percentage discount that also requires a minimum quantity of eligible items.
    min_items: Mapped[int | None] = mapped_column(SmallInteger)

    created_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("profiles.id", ondelete="SET NULL")
    )

    usages: Mapped[list[CouponUsage]] = relationship(back_populates="coupon", lazy="noload")

    def is_within_window(self, now: datetime) -> bool:
        if self.starts_at is not None and now < self.starts_at:
            return False
        if self.expires_at is not None and now > self.expires_at:
            return False
        return True


class CouponUsage(UUIDPrimaryKeyMixin, Base):
    """One row per order that consumed a coupon.

    The unique constraint on ``order_id`` is what makes coupon application
    idempotent: a retried payment or a replayed webhook cannot consume a second
    use of the same order.
    """

    __tablename__ = "coupon_usages"
    __table_args__ = (
        UniqueConstraint("order_id", name="uq_coupon_usages_order_id"),
        Index("ix_coupon_usages_coupon_profile", "coupon_id", "profile_id"),
    )

    coupon_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("coupons.id", ondelete="CASCADE"), nullable=False
    )
    profile_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("profiles.id", ondelete="CASCADE"), nullable=False
    )
    order_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("orders.id", ondelete="CASCADE"), nullable=False
    )
    #: Discount actually granted, captured for reporting.
    discount_amount: Mapped[int] = mapped_column(Integer, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()"), nullable=False
    )

    coupon: Mapped[Coupon] = relationship(back_populates="usages", lazy="joined")
    order: Mapped[Order] = relationship(back_populates="coupon_usage", lazy="noload")
