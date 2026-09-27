"""Catalogue: categories, tags, products, variants, images and inventory.

Two integrity rules are enforced by the database rather than by application
code, because both are violated under concurrency:

* ``inventory.available`` is a **generated column** (``quantity - reserved``).
  Nothing can write a stock figure that disagrees with itself.
* ``products.price_min`` is maintained by a trigger on ``product_variants``,
  because a generated column cannot reference another table. Listings render
  "from ₹X" from this column, so it must be correct the instant a variant price
  changes - not on the next request.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Computed,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, TSVECTOR
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin, enum_column
from app.models.enums import InventoryReason, ProductStatus, VariantStatus

if TYPE_CHECKING:
    from app.models.commerce import CartItem, WishlistItem
    from app.models.orders import OrderItem
    from app.models.review import Review


class Category(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Self-referencing tree. ``path`` stores the materialised ancestor chain."""

    __tablename__ = "categories"
    __table_args__ = (
        UniqueConstraint("slug", name="uq_categories_slug"),
        Index("ix_categories_parent_id", "parent_id"),
        Index("ix_categories_is_active_position", "is_active", "position"),
    )

    name: Mapped[str] = mapped_column(String(120), nullable=False)
    slug: Mapped[str] = mapped_column(String(140), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    parent_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("categories.id", ondelete="RESTRICT")
    )
    #: Comma separated ancestor ids, root first, excluding self.
    path: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
    position: Mapped[int] = mapped_column(SmallInteger, nullable=False, server_default="0")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")
    image_url: Mapped[str | None] = mapped_column(Text)

    # SEO
    seo_title: Mapped[str | None] = mapped_column(String(180))
    seo_description: Mapped[str | None] = mapped_column(String(320))

    parent: Mapped[Category | None] = relationship(
        back_populates="children", remote_side="Category.id", lazy="joined"
    )
    children: Mapped[list[Category]] = relationship(back_populates="parent", lazy="noload")
    products: Mapped[list[Product]] = relationship(back_populates="category", lazy="noload")

    def ancestor_ids(self) -> list[uuid.UUID]:
        return [uuid.UUID(part) for part in self.path.split(",") if part]


class Tag(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "tags"
    __table_args__ = (UniqueConstraint("slug", name="uq_tags_slug"),)

    name: Mapped[str] = mapped_column(String(64), nullable=False)
    slug: Mapped[str] = mapped_column(String(80), nullable=False)


class Product(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "products"
    __table_args__ = (
        UniqueConstraint("slug", name="uq_products_slug"),
        UniqueConstraint("sku", name="uq_products_sku"),
        CheckConstraint("base_price >= 0", name="base_price_non_negative"),
        CheckConstraint(
            "compare_at_price IS NULL OR compare_at_price >= base_price",
            name="compare_at_above_base",
        ),
        Index("ix_products_category_id", "category_id"),
        Index("ix_products_status_created_at", "status", "created_at"),
        Index("ix_products_is_featured_status", "is_featured", "status"),
        Index("ix_products_brand", "brand"),
        # Composite index matching the default listing order (newest first)
        # filtered to live products, so the planner never scans drafts.
        Index(
            "ix_products_listing",
            "status",
            "created_at",
            postgresql_where=text("status = 'ACTIVE'"),
        ),
        Index("ix_products_search", "search_vector", postgresql_using="gin"),
    )

    title: Mapped[str] = mapped_column(String(200), nullable=False)
    slug: Mapped[str] = mapped_column(String(220), nullable=False)
    subtitle: Mapped[str | None] = mapped_column(String(240))
    short_description: Mapped[str | None] = mapped_column(String(400))
    #: Long form copy. Markdown subset, sanitised on render.
    description: Mapped[str] = mapped_column(Text, nullable=False, server_default="")

    sku: Mapped[str] = mapped_column(String(64), nullable=False)
    brand: Mapped[str | None] = mapped_column(String(80))
    category_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("categories.id", ondelete="RESTRICT"), nullable=False
    )

    #: Minor units. The price actually charged when a variant has no override.
    base_price: Mapped[int] = mapped_column(BigInteger, nullable=False)
    #: Minor units. Struck-through reference price. Must be >= base_price.
    compare_at_price: Mapped[int | None] = mapped_column(BigInteger)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, server_default="INR")

    status: Mapped[ProductStatus] = mapped_column(
        enum_column(ProductStatus, "product_status", default=ProductStatus.DRAFT),
        nullable=False,
        server_default=ProductStatus.DRAFT.value,
    )
    is_featured: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    #: Free-form merchandising attributes surfaced on the PDP spec table.
    specs: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False, server_default="{}")

    # SEO
    seo_title: Mapped[str | None] = mapped_column(String(180))
    seo_description: Mapped[str | None] = mapped_column(String(320))
    seo_keywords: Mapped[list[str] | None] = mapped_column(JSONB)

    search_vector: Mapped[object | None] = mapped_column(TSVECTOR, nullable=True)

    category: Mapped[Category] = relationship(back_populates="products", lazy="joined")
    variants: Mapped[list[ProductVariant]] = relationship(
        back_populates="product",
        cascade="all, delete-orphan",
        lazy="selectin",
        order_by="ProductVariant.position",
    )
    images: Mapped[list[ProductImage]] = relationship(
        back_populates="product",
        cascade="all, delete-orphan",
        lazy="selectin",
        order_by="ProductImage.position",
    )
    tags: Mapped[list[Tag]] = relationship(secondary="product_tags", lazy="selectin")
    reviews: Mapped[list[Review]] = relationship(back_populates="product", lazy="noload")

    #: Maintained by ``trg_products_price_min``. Never written by the app.
    price_min: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    price_max: Mapped[int | None] = mapped_column(BigInteger, nullable=True)

    @property
    def primary_image(self) -> ProductImage | None:
        for image in self.images:
            if image.is_primary:
                return image
        return self.images[0] if self.images else None

    @property
    def discount_percent(self) -> int:
        if not self.compare_at_price or self.compare_at_price <= self.base_price:
            return 0
        reference = self.compare_at_price or self.base_price
        return round((reference - self.base_price) * 100 / reference)

    def effective_price(self) -> int:
        return self.price_min or self.base_price

    def in_stock(self) -> bool:
        return any(v.is_purchasable and v.available_quantity > 0 for v in self.variants)


class ProductTag(Base):
    __tablename__ = "product_tags"
    __table_args__ = (Index("ix_product_tags_tag_id", "tag_id"),)

    product_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("products.id", ondelete="CASCADE"), primary_key=True
    )
    tag_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("tags.id", ondelete="CASCADE"), primary_key=True
    )


class ProductVariant(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A purchasable configuration: colour, size, capacity, or a combination.

    ``price`` is an *override* of the product's base price. When null the
    variant inherits ``products.base_price``. The effective price is resolved by
    a generated column so no two code paths can disagree about it.
    """

    __tablename__ = "product_variants"
    __table_args__ = (
        UniqueConstraint("sku", name="uq_product_variants_sku"),
        CheckConstraint("price_override IS NULL OR price_override >= 0", name="price_non_negative"),
        Index("ix_product_variants_product_id", "product_id"),
        Index("ix_product_variants_product_id_status", "product_id", "status"),
        Index("ix_product_variants_sku_lookup", "sku", unique=True),
    )

    product_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("products.id", ondelete="CASCADE"), nullable=False
    )
    sku: Mapped[str] = mapped_column(String(64), nullable=False)
    title: Mapped[str] = mapped_column(String(160), nullable=False)
    #: e.g. {"Colour": "Midnight", "Size": "M"} - the UI renders these directly.
    attributes: Mapped[dict[str, object]] = mapped_column(
        JSONB, nullable=False, server_default="{}"
    )
    #: Minor units. NULL means "inherit the product price".
    price_override: Mapped[int | None] = mapped_column(BigInteger)
    compare_at_price: Mapped[int | None] = mapped_column(BigInteger)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, server_default="INR")

    status: Mapped[VariantStatus] = mapped_column(
        enum_column(VariantStatus, "variant_status", default=VariantStatus.ACTIVE),
        nullable=False,
        server_default=VariantStatus.ACTIVE.value,
    )
    position: Mapped[int] = mapped_column(SmallInteger, nullable=False, server_default="0")
    is_default: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    #: Units below this threshold raise a low-stock alert.
    low_stock_threshold: Mapped[int] = mapped_column(Integer, nullable=False, server_default="3")
    weight_grams: Mapped[int | None] = mapped_column(Integer)

    product: Mapped[Product] = relationship(back_populates="variants", lazy="joined")
    inventory: Mapped[Inventory | None] = relationship(
        back_populates="variant", uselist=False, lazy="joined", cascade="all, delete-orphan"
    )
    cart_items: Mapped[list[CartItem]] = relationship(back_populates="variant", lazy="noload")
    wishlist_items: Mapped[list[WishlistItem]] = relationship(
        back_populates="variant", lazy="noload"
    )
    order_items: Mapped[list[OrderItem]] = relationship(back_populates="variant", lazy="noload")

    @property
    def is_purchasable(self) -> bool:
        return self.status == VariantStatus.ACTIVE

    @property
    def available_quantity(self) -> int:
        return self.inventory.available_quantity if self.inventory else 0

    def effective_price(self) -> int:
        if self.price_override is not None:
            return self.price_override
        return self.product.base_price if self.product else 0

    def effective_compare_at(self) -> int | None:
        if self.compare_at_price is not None:
            return self.compare_at_price
        return self.product.compare_at_price if self.product else None

    def option(self, key: str) -> str | None:
        value = self.attributes.get(key)
        return str(value) if value is not None else None


class ProductImage(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "product_images"
    __table_args__ = (
        Index("ix_product_images_product_id_position", "product_id", "position"),
        # Exactly one primary image per product.
        Index(
            "uq_product_images_one_primary",
            "product_id",
            unique=True,
            postgresql_where=text("is_primary"),
        ),
    )

    product_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("products.id", ondelete="CASCADE"), nullable=False
    )
    #: Public URL or, for the private bucket, a path resolved to a signed URL.
    url: Mapped[str] = mapped_column(Text, nullable=False)
    storage_path: Mapped[str | None] = mapped_column(Text)
    alt_text: Mapped[str] = mapped_column(String(200), nullable=False, server_default="")
    position: Mapped[int] = mapped_column(SmallInteger, nullable=False, server_default="0")
    is_primary: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    width: Mapped[int | None] = mapped_column(Integer)
    height: Mapped[int | None] = mapped_column(Integer)
    blur_data_url: Mapped[str | None] = mapped_column(Text)

    product: Mapped[Product] = relationship(back_populates="images", lazy="joined")


class Inventory(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Server-controlled stock. One row per variant.

    ``available`` is generated as ``quantity - reserved`` so the three columns
    can never disagree. Reserving stock is a single conditional UPDATE (see
    ``InventoryService.reserve``) which is what makes overselling impossible.
    """

    __tablename__ = "inventory"
    __table_args__ = (
        CheckConstraint("quantity >= 0", name="quantity_non_negative"),
        CheckConstraint("reserved >= 0", name="reserved_non_negative"),
        CheckConstraint("reserved <= quantity", name="reserved_not_over_quantity"),
        Index("ix_inventory_variant_id", "variant_id", unique=True),
        Index("ix_inventory_low_stock", "low_stock_threshold"),
    )

    variant_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("product_variants.id", ondelete="CASCADE"), nullable=False, unique=True
    )
    #: Physical units on hand.
    quantity: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    #: Units held for in-flight payments. Released on failure or expiry.
    reserved: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    low_stock_threshold: Mapped[int] = mapped_column(Integer, nullable=False, server_default="3")
    #: Reorder point used by the low-stock job and the admin dashboard.
    reorder_point: Mapped[int] = mapped_column(Integer, nullable=False, server_default="5")
    #: Sellable units right now. A *generated* column, so no code path - ours,
    #: a psql session, or a future service - can write a stock figure that
    #: disagrees with itself. This is what oversell protection is checked against.
    available: Mapped[int] = mapped_column(Computed("quantity - reserved", persisted=True))

    variant: Mapped[ProductVariant] = relationship(back_populates="inventory", lazy="joined")

    @property
    def is_low_stock(self) -> bool:
        return self.available <= self.low_stock_threshold

    @property
    def is_out_of_stock(self) -> bool:
        return self.available <= 0


class InventoryMovement(UUIDPrimaryKeyMixin, Base):
    """Append-only ledger of every stock change.

    Reconciliation (``reconcile_inventory`` job) compares the running sum of
    movements against ``inventory.quantity``. A mismatch is a bug report, not a
    silent drift.
    """

    __tablename__ = "inventory_movements"
    __table_args__ = (
        Index("ix_inventory_movements_variant_created", "variant_id", "created_at"),
        Index("ix_inventory_movements_order_id", "order_id"),
    )

    variant_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("product_variants.id", ondelete="CASCADE"), nullable=False
    )
    #: Signed delta applied to ``inventory.quantity``.
    delta: Mapped[int] = mapped_column(Integer, nullable=False)
    quantity_after: Mapped[int] = mapped_column(Integer, nullable=False)
    reserved_delta: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    reason: Mapped[InventoryReason] = mapped_column(
        enum_column(InventoryReason, "inventory_reason"), nullable=False
    )
    order_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("orders.id", ondelete="SET NULL"))
    note: Mapped[str | None] = mapped_column(String(240))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
