"""B2B quote requests, contact messages, industries and the knowledge base.

These are the tables that make this a B2B signage business rather than a generic
store. The central one is ``quote_requests``: a factory ordering 200 boards does
not want a checkout, they want a quote, and forcing them through a cart is how
you lose the sale.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin, enum_column
from app.models.catalog import Product, ProductVariant
from app.models.enums import QuoteStatus
from app.models.identity import Profile


# ===========================================================================
# Bulk quotes
# ===========================================================================
class QuoteRequest(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A request for a bulk/custom quote.

    Reachable from any product page ("Need Bulk Quantity?") or from
    ``/bulk-order`` without an account, so it doubles as a lead-capture form.
    ``product_id`` and ``variant_id`` are optional: a buyer often asks about
    "200 ACP boards" before choosing a specific design.
    """

    __tablename__ = "quote_requests"
    __table_args__ = (
        # One open request per email per product, so a double-clicked form does
        # not create two rows that staff chase separately.
        Index(
            "uq_quote_requests_open_per_email",
            "email",
            "product_id",
            unique=True,
            postgresql_where=text("status = 'NEW'"),
        ),
        Index("ix_quote_requests_status_created", "status", "created_at"),
        Index("ix_quote_requests_assigned", "assigned_to_profile_id", "status"),
        CheckConstraint("quantity IS NULL OR quantity > 0", name="quantity_positive"),
        # A GSTIN is 15 characters: 2 state, 10 PAN, 1 entity, 1 Z, 1 check.
        CheckConstraint(
            "gstin IS NULL OR gstin ~ '^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z][0-9A-Z]Z[0-9A-Z]$'",
            name="gstin_format",
        ),
    )

    # --- who ---
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    company: Mapped[str | None] = mapped_column(String(200))
    email: Mapped[str] = mapped_column(String(320), nullable=False)
    phone: Mapped[str] = mapped_column(String(24), nullable=False)
    city: Mapped[str | None] = mapped_column(String(96))
    state: Mapped[str | None] = mapped_column(String(96))
    gstin: Mapped[str | None] = mapped_column(String(15))

    # --- what ---
    product_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("products.id", ondelete="SET NULL")
    )
    variant_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("product_variants.id", ondelete="SET NULL")
    )
    product_name: Mapped[str | None] = mapped_column(
        String(200), comment="Snapshot, so the request survives product deletion"
    )
    quantity: Mapped[int | None] = mapped_column(Integer)
    preferred_material: Mapped[str | None] = mapped_column(String(64))
    preferred_size: Mapped[str | None] = mapped_column(String(32))
    message: Mapped[str | None] = mapped_column(Text)

    # --- workflow ---
    status: Mapped[QuoteStatus] = mapped_column(
        enum_column(QuoteStatus, "quote_status", default=QuoteStatus.NEW),
        nullable=False,
        server_default=QuoteStatus.NEW.value,
    )
    assigned_to_profile_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("profiles.id", ondelete="SET NULL")
    )
    internal_notes: Mapped[str | None] = mapped_column(Text)
    #: Set when staff quote a price, so the customer sees an amount.
    quoted_amount: Mapped[int | None] = mapped_column(Integer, comment="Minor units (paise)")
    quoted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    contacted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    #: Populated when a quote becomes an order, for conversion reporting.
    converted_order_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("orders.id", ondelete="SET NULL")
    )
    reference: Mapped[str] = mapped_column(
        String(24), nullable=False, unique=True, comment="Human readable, e.g. QT-8F3A2C"
    )
    source: Mapped[str | None] = mapped_column(
        String(48), comment="product_page | bulk_order | contact"
    )

    assigned_to: Mapped[Profile | None] = relationship(
        foreign_keys=[assigned_to_profile_id], lazy="joined"
    )
    product: Mapped[Product | None] = relationship(lazy="joined")
    variant: Mapped[ProductVariant | None] = relationship(lazy="joined")

    def is_open(self) -> bool:
        return self.status in {
            QuoteStatus.NEW,
            QuoteStatus.CONTACTED,
            QuoteStatus.QUOTED,
        }


class ContactMessage(UUIDPrimaryKeyMixin, Base):
    """General contact-form submissions."""

    __tablename__ = "contact_messages"
    __table_args__ = (
        Index("ix_contact_messages_is_read", "is_read"),
        CheckConstraint("char_length(body) BETWEEN 1 AND 4000", name="body_length"),
    )

    name: Mapped[str] = mapped_column(String(160), nullable=False)
    email: Mapped[str] = mapped_column(String(320), nullable=False)
    phone: Mapped[str | None] = mapped_column(String(24))
    company: Mapped[str | None] = mapped_column(String(200))
    subject: Mapped[str | None] = mapped_column(String(200))
    body: Mapped[str] = mapped_column(Text, nullable=False)
    #: Which page the form was submitted from, for attribution.
    source_page: Mapped[str | None] = mapped_column(String(240))
    is_read: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    handled_by_profile_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("profiles.id", ondelete="SET NULL")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()"), nullable=False
    )


# ===========================================================================
# Industries
# ===========================================================================
class Industry(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A landing page for a customer segment, e.g. Manufacturing.

    The body is Markdown so a non-engineer can edit it in the admin and have it
    render safely (sanitised subset, no raw HTML).
    """

    __tablename__ = "industries"
    __table_args__ = (
        UniqueConstraint("slug", name="uq_industries_slug"),
        Index("ix_industries_is_active_position", "is_active", "position"),
    )

    name: Mapped[str] = mapped_column(String(120), nullable=False)
    slug: Mapped[str] = mapped_column(String(140), nullable=False)
    #: One-line promise used on the card and in the meta description.
    tagline: Mapped[str | None] = mapped_column(String(240))
    #: What this segment actually needs, in their language.
    summary: Mapped[str | None] = mapped_column(Text)
    body: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
    hero_image_url: Mapped[str | None] = mapped_column(Text)
    icon: Mapped[str | None] = mapped_column(String(48), comment="lucide icon name, e.g. 'factory'")
    position: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")
    seo_title: Mapped[str | None] = mapped_column(String(180))
    seo_description: Mapped[str | None] = mapped_column(String(320))

    products: Mapped[list[Product]] = relationship(
        secondary="industry_products",
        lazy="selectin",
        order_by="IndustryProduct.position",
    )


class IndustryProduct(Base):
    """Curated product picks for an industry page.

    Explicitly *not* derived from category membership: a chemical plant needs a
    specific hand-picked set of MSDS boards, not "everything in Lab Safety".
    """

    __tablename__ = "industry_products"
    __table_args__ = (Index("ix_industry_products_industry_position", "industry_id", "position"),)

    industry_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("industries.id", ondelete="CASCADE"), primary_key=True
    )
    product_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("products.id", ondelete="CASCADE"), primary_key=True
    )
    #: Why this product is relevant to this industry. Renders as a caption.
    note: Mapped[str | None] = mapped_column(String(240))
    position: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")


# ===========================================================================
# Knowledge base / blog
# ===========================================================================
class BlogCategory(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "blog_categories"
    __table_args__ = (UniqueConstraint("slug", name="uq_blog_categories_slug"),)

    name: Mapped[str] = mapped_column(String(120), nullable=False)
    slug: Mapped[str] = mapped_column(String(140), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    seo_title: Mapped[str | None] = mapped_column(String(180))
    seo_description: Mapped[str | None] = mapped_column(String(320))


class BlogPost(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "blog_posts"
    __table_args__ = (
        UniqueConstraint("slug", name="uq_blog_posts_slug"),
        CheckConstraint("char_length(title) BETWEEN 1 AND 200", name="title_length"),
        CheckConstraint("char_length(excerpt) BETWEEN 1 AND 400", name="excerpt_length"),
        Index("ix_blog_posts_status_published", "status", "published_at"),
        Index("ix_blog_posts_published_at", "published_at"),
    )

    title: Mapped[str] = mapped_column(String(200), nullable=False)
    slug: Mapped[str] = mapped_column(String(220), nullable=False)
    excerpt: Mapped[str] = mapped_column(String(400), nullable=False)
    #: Markdown body, rendered through a sanitising subset.
    body: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
    cover_image_url: Mapped[str | None] = mapped_column(Text)
    cover_image_alt: Mapped[str | None] = mapped_column(String(200))
    status: Mapped[str] = mapped_column(String(16), nullable=False, server_default="DRAFT")
    #: The live site does not display authors, so this is optional and is NOT
    #: populated with an invented name.
    author_name: Mapped[str | None] = mapped_column(String(120))
    author_profile_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("profiles.id", ondelete="SET NULL")
    )
    reading_minutes: Mapped[int | None] = mapped_column(Integer)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    #: Compliance deadline this article is written against, e.g. the OSHA
    #: HazCom / GHS Rev 7 date. Surfaced as a badge in the UI.
    compliance_deadline: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    seo_title: Mapped[str | None] = mapped_column(String(180))
    seo_description: Mapped[str | None] = mapped_column(String(320))
    #: FAQ entries rendered as FAQPage structured data.
    faq: Mapped[list[dict[str, str]] | None] = mapped_column(JSONB)

    categories: Mapped[list[BlogCategory]] = relationship(
        secondary="blog_post_categories", lazy="selectin"
    )
    products: Mapped[list[Product]] = relationship(
        secondary="blog_post_products",
        lazy="selectin",
        order_by="BlogPostProduct.position",
    )

    def is_published(self) -> bool:
        return self.status == "PUBLISHED"


class BlogPostCategory(Base):
    __tablename__ = "blog_post_categories"
    __table_args__ = (Index("ix_blog_post_categories_category_id", "category_id"),)

    post_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("blog_posts.id", ondelete="CASCADE"), primary_key=True
    )
    category_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("blog_categories.id", ondelete="CASCADE"), primary_key=True
    )


class BlogPostProduct(Base):
    """Products mentioned in an article, for the "Shop this article" rail."""

    __tablename__ = "blog_post_products"
    __table_args__ = (Index("ix_blog_post_products_post_position", "post_id", "position"),)

    post_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("blog_posts.id", ondelete="CASCADE"), primary_key=True
    )
    product_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("products.id", ondelete="CASCADE"), primary_key=True
    )
    position: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")


# ===========================================================================
# Recently viewed
# ===========================================================================
class ProductView(UUIDPrimaryKeyMixin, Base):
    """Recently-viewed tracking.

    ``session_key`` is an anonymous id for guests and the profile id for
    customers, so the rail works for both without asking anyone to register.
    """

    __tablename__ = "product_views"
    __table_args__ = (
        Index("ix_product_views_session_recent", "session_key", "viewed_at"),
        Index("ix_product_views_product_id", "product_id"),
    )

    product_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("products.id", ondelete="CASCADE"), nullable=False
    )
    profile_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("profiles.id", ondelete="CASCADE")
    )
    #: Anonymous visitor id, or the profile id as a string. Indexed for the rail.
    session_key: Mapped[str] = mapped_column(String(64), nullable=False)
    viewed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()"), nullable=False
    )
    #: How many times this visitor has viewed the product, for weighting.
    view_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="1")
