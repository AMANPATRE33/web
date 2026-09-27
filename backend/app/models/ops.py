"""Operational tables: transactional outbox, idempotency keys, webhooks, sessions.

The outbox is what makes background jobs reliable rather than best-effort. When
an order is marked paid, the API writes an ``OutboxEvent`` **in the same
transaction** and returns. A worker drains the outbox and enqueues the email.
If the worker is down, the email is not lost - it is delivered when the worker
comes back. Without this, a Redis hiccup at the moment of purchase means a
customer who paid never gets a confirmation.

Idempotency is the same idea applied to inbound calls: a Razorpay webhook
delivered twice, or a client retrying a POST, is recorded here and the second
attempt replays the first result instead of doing the work again.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    SmallInteger,
    String,
    Text,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, UUIDPrimaryKeyMixin, enum_column
from app.models.enums import EmailKind, OutboxStatus


class OutboxEvent(UUIDPrimaryKeyMixin, Base):
    """A side effect that must happen, recorded transactionally."""

    __tablename__ = "outbox_events"
    __table_args__ = (
        Index("ix_outbox_events_status_created", "status", "created_at"),
        Index("ix_outbox_events_dedupe_key", "dedupe_key", unique=True),
    )

    #: Job name understood by ``app.workers.jobs``.
    topic: Mapped[str] = mapped_column(String(64), nullable=False)
    payload: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False)
    status: Mapped[OutboxStatus] = mapped_column(
        enum_column(OutboxStatus, "outbox_status", default=OutboxStatus.PENDING),
        nullable=False,
        server_default=OutboxStatus.PENDING.value,
    )
    #: Collapse repeated intents, e.g. "order_paid_email:{order_id}".
    dedupe_key: Mapped[str | None] = mapped_column(String(160))
    attempts: Mapped[int] = mapped_column(SmallInteger, nullable=False, server_default="0")
    last_error: Mapped[str | None] = mapped_column(Text)
    available_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()"), nullable=False
    )
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()"), nullable=False
    )

    def job_name(self) -> str:
        return f"outbox_dispatch:{self.topic}"


class IdempotencyKey(UUIDPrimaryKeyMixin, Base):
    """Records the outcome of a mutating request keyed by a client token."""

    __tablename__ = "idempotency_keys"
    __table_args__ = (
        # Scope + key is unique, so two different endpoints cannot collide.
        Index("uq_idempotency_keys_scope_key", "scope", "key", unique=True),
        Index("ix_idempotency_keys_expires_at", "expires_at"),
    )

    scope: Mapped[str] = mapped_column(String(64), nullable=False)
    key: Mapped[str] = mapped_column(String(128), nullable=False)
    request_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    response_status: Mapped[int] = mapped_column(Integer, nullable=False)
    response_body: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()"), nullable=False
    )
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now() + interval '48 hours'"), nullable=False
    )


class WebhookEvent(UUIDPrimaryKeyMixin, Base):
    """Received payment gateway events, retained for reconciliation."""

    __tablename__ = "webhook_events"
    __table_args__ = (
        Index("uq_webhook_events_provider_event", "provider", "provider_event_id", unique=True),
        Index("ix_webhook_events_received_at", "received_at"),
    )

    provider: Mapped[str] = mapped_column(String(32), nullable=False, server_default="razorpay")
    provider_event_id: Mapped[str] = mapped_column(String(128), nullable=False)
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    #: Verified signature. An unverified payload is never parsed for business logic.
    signature: Mapped[str | None] = mapped_column(String(256))
    payload: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False)
    processed: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    processing_error: Mapped[str | None] = mapped_column(Text)
    attempts: Mapped[int] = mapped_column(SmallInteger, nullable=False, server_default="0")
    received_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()"), nullable=False
    )


class EmailLog(UUIDPrimaryKeyMixin, Base):
    """Audit trail of every transactional email, for support and deliverability."""

    __tablename__ = "email_logs"
    __table_args__ = (
        Index("ix_email_logs_kind_created", "kind", "created_at"),
        Index("ix_email_logs_recipient", "recipient"),
    )

    kind: Mapped[EmailKind] = mapped_column(enum_column(EmailKind, "email_kind"), nullable=False)
    recipient: Mapped[str] = mapped_column(String(320), nullable=False)
    subject: Mapped[str] = mapped_column(String(240), nullable=False)
    provider: Mapped[str] = mapped_column(String(32), nullable=False)
    provider_message_id: Mapped[str | None] = mapped_column(String(160))
    status: Mapped[str] = mapped_column(String(24), nullable=False)
    error: Mapped[str | None] = mapped_column(Text)
    order_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("orders.id", ondelete="SET NULL"))
    profile_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("profiles.id", ondelete="SET NULL")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()"), nullable=False
    )


class IdempotentCounter(Base):
    """Atomic counter used for human friendly, non-enumerable order numbers.

    A sequence would let a customer infer daily volume by requesting
    ``/order/SF-000123``. This counter is reserved inside the order transaction
    and rendered as a short random-suffixed reference instead.
    """

    __tablename__ = "id_counters"
    __table_args__ = ()

    name: Mapped[str] = mapped_column(String(48), primary_key=True)
    value: Mapped[int] = mapped_column(nullable=False, server_default="0")


class StockNotification(UUIDPrimaryKeyMixin, Base):
    """Back-in-stock waitlist for a variant that a customer wishlisted."""

    __tablename__ = "stock_notifications"
    __table_args__ = (
        Index(
            "uq_stock_notifications_variant_profile",
            "variant_id",
            "profile_id",
            unique=True,
        ),
    )

    variant_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("product_variants.id", ondelete="CASCADE"), nullable=False
    )
    profile_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("profiles.id", ondelete="CASCADE"), nullable=False
    )
    email: Mapped[str] = mapped_column(String(320), nullable=False)
    notified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()"), nullable=False
    )


class UserSession(UUIDPrimaryKeyMixin, Base):
    """Lightweight record of authenticated sessions, for security review.

    Supabase remains the authority on whether a token is valid; this table
    records what the API has seen so an administrator can spot a token being
    replayed from an unexpected client or IP.
    """

    __tablename__ = "user_sessions"
    __table_args__ = (
        Index("ix_user_sessions_profile_started", "profile_id", "started_at"),
        Index("ix_user_sessions_last_seen", "last_seen_at"),
    )

    profile_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("profiles.id", ondelete="CASCADE"), nullable=False
    )
    #: SHA-256 of the session id. Raw tokens are never stored.
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    ip_address: Mapped[str | None] = mapped_column(String(64))
    user_agent: Mapped[str | None] = mapped_column(String(400))
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()"), nullable=False
    )
    last_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()"), nullable=False
    )
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
