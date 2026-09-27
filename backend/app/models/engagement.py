"""Customer reviews, newsletter subscribers and the privileged audit log.

``reviews.verified_purchase`` is a stored column rather than something computed
at read time, because the rule is point-in-time: "had this account completed a
paid order containing this variant before the review was written". Recomputing it
later would silently upgrade old reviews once a customer bought the product, and
would silently *downgrade* nothing - two different wrong answers. The
``recalculate_verified_purchase`` job re-evaluates it for newly completed
orders and never revokes a flag that was already granted.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin, enum_column
from app.models.catalog import Product, ProductVariant  # noqa: F401  (relationship targets)
from app.models.enums import ReviewStatus, SubscriberStatus
from app.models.identity import Profile
from app.models.orders import Order  # noqa: F401  (relationship targets)


class Review(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "reviews"
    __table_args__ = (
        # One review per customer per product. Variants are aggregated at
        # product level because a rating for "the headphones" is about the
        # product, not one colourway.
        UniqueConstraint("product_id", "profile_id", name="uq_reviews_product_profile"),
        CheckConstraint("rating >= 1 AND rating <= 5", name="rating_between_1_and_5"),
        CheckConstraint("char_length(title) BETWEEN 1 AND 140", name="title_length"),
        CheckConstraint("char_length(comment) BETWEEN 1 AND 4000", name="comment_length"),
        Index("ix_reviews_product_status_created", "product_id", "status", "created_at"),
        Index("ix_reviews_status", "status"),
    )

    product_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("products.id", ondelete="CASCADE"), nullable=False
    )
    profile_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("profiles.id", ondelete="CASCADE"), nullable=False
    )
    #: NULL when the review concerns the product generally.
    variant_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("product_variants.id", ondelete="SET NULL")
    )
    order_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("orders.id", ondelete="SET NULL"))

    rating: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    title: Mapped[str] = mapped_column(String(140), nullable=False)
    comment: Mapped[str] = mapped_column(Text, nullable=False)

    status: Mapped[ReviewStatus] = mapped_column(
        enum_column(ReviewStatus, "review_status", default=ReviewStatus.PENDING),
        nullable=False,
        server_default=ReviewStatus.PENDING.value,
    )
    verified_purchase: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")

    # Moderation
    moderated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    moderated_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("profiles.id", ondelete="SET NULL")
    )
    moderation_note: Mapped[str | None] = mapped_column(String(400))
    helpful_count: Mapped[int] = mapped_column(SmallInteger, nullable=False, server_default="0")

    product: Mapped[Product] = relationship(back_populates="reviews", lazy="joined")
    #: ``reviews`` has two foreign keys to ``profiles`` (the author and the
    #: moderator), so the join condition has to be stated explicitly.
    author: Mapped[Profile] = relationship(foreign_keys=[profile_id], lazy="joined", viewonly=True)
    moderator: Mapped[Profile | None] = relationship(
        foreign_keys=[moderated_by], lazy="joined", viewonly=True
    )


class ProductRatingSummary(Base):
    """Denormalised rating aggregates, recomputed whenever a review changes.

    Reading ``AVG(rating) COUNT(*)`` over a large ``reviews`` table on every
    product card render is the classic N+1 that quietly ruins a listing page.
    """

    __tablename__ = "product_rating_summaries"
    __table_args__ = ()

    product_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("products.id", ondelete="CASCADE"), primary_key=True
    )
    average_rating: Mapped[float] = mapped_column(
        Float, nullable=False, server_default="0", comment="Rounded to 2dp on write"
    )
    review_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    #: Counts for 1..5 stars, index 0 = one star. Drives the rating histogram.
    distribution: Mapped[list[int]] = mapped_column(
        ARRAY(Integer), nullable=False, server_default="{}"
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=text("now()"),
        onupdate=text("now()"),
        nullable=False,
    )


class NewsletterSubscriber(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "newsletter_subscribers"
    __table_args__ = (
        UniqueConstraint("email", name="uq_newsletter_subscribers_email"),
        Index("ix_newsletter_subscribers_status", "status"),
    )

    email: Mapped[str] = mapped_column(String(320), nullable=False)
    status: Mapped[SubscriberStatus] = mapped_column(
        enum_column(SubscriberStatus, "subscriber_status", default=SubscriberStatus.PENDING),
        nullable=False,
        server_default=SubscriberStatus.PENDING.value,
    )
    source: Mapped[str | None] = mapped_column(String(64))
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    unsubscribed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    unsubscribe_token: Mapped[str] = mapped_column(String(64), nullable=False)
    #: Set when a signup came from a user who already had an account.
    profile_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("profiles.id", ondelete="SET NULL")
    )


class AuditLog(UUIDPrimaryKeyMixin, Base):
    """Every privileged mutation, with the before and after payloads.

    Written inside the same transaction as the change it records. If the
    transaction rolls back, so does the audit row - which is correct: the change
    did not happen.
    """

    __tablename__ = "audit_logs"
    __table_args__ = (
        Index("ix_audit_logs_actor_created", "actor_profile_id", "created_at"),
        Index("ix_audit_logs_entity", "entity_type", "entity_id"),
        Index("ix_audit_logs_action", "action"),
    )

    actor_profile_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("profiles.id", ondelete="SET NULL")
    )
    #: Null for system actions (workers, webhooks).
    actor_label: Mapped[str] = mapped_column(String(64), nullable=False, server_default="system")
    action: Mapped[str] = mapped_column(String(64), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(48), nullable=False)
    entity_id: Mapped[str | None] = mapped_column(String(64))
    before: Mapped[dict[str, object] | None] = mapped_column(JSONB, nullable=True)
    after: Mapped[dict[str, object] | None] = mapped_column(JSONB, nullable=True)
    ip_address: Mapped[str | None] = mapped_column(String(64))
    user_agent: Mapped[str | None] = mapped_column(String(400))
    request_id: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()"), nullable=False
    )
