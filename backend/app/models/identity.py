"""Customer identity and addresses.

``profiles.id`` is the Supabase Auth user id. The foreign key to
``auth.users`` is intentionally *not* declared in the Alembic chain: the
``auth`` schema only exists on Supabase, so declaring it would make the
migrations unrunnable against a plain PostgreSQL instance. The constraint is
added by ``database/sql/004_auth_fk.sql``, which is guarded by a check for the
schema's existence and is therefore a no-op locally.

The converse guarantee - that a profile always exists for an authenticated
user - is handled in application code by ``ensure_profile()``, which runs on
every authenticated request. A Supabase trigger in the same SQL script provides
a second, independent path for rows created outside the API.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import CITEXT
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin, enum_column
from app.models.enums import AddressType, UserRole

if TYPE_CHECKING:
    from app.models.commerce import Cart, Wishlist
    from app.models.orders import Order


class Profile(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Customer or staff account, mirroring the Supabase Auth user."""

    __tablename__ = "profiles"
    __table_args__ = (
        UniqueConstraint("email", name="uq_profiles_email"),
        Index("ix_profiles_role", "role"),
        Index("ix_profiles_created_at", "created_at"),
    )

    email: Mapped[str] = mapped_column(CITEXT, nullable=False)
    full_name: Mapped[str | None] = mapped_column(String(160))
    phone: Mapped[str | None] = mapped_column(String(24))
    avatar_url: Mapped[str | None] = mapped_column(Text)

    role: Mapped[UserRole] = mapped_column(
        enum_column(UserRole, "user_role", default=UserRole.CUSTOMER),
        nullable=False,
        server_default=UserRole.CUSTOMER.value,
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")
    email_verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    phone_verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    marketing_opt_in: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="false"
    )

    # Soft-lock. A deactivated account keeps its order history intact.
    deactivated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    addresses: Mapped[list[Address]] = relationship(
        back_populates="profile",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    orders: Mapped[list[Order]] = relationship(back_populates="profile", lazy="noload")
    cart: Mapped[Cart | None] = relationship(back_populates="profile", uselist=False)
    wishlist: Mapped[Wishlist | None] = relationship(
        back_populates="profile", uselist=False
    )

    @property
    def is_admin(self) -> bool:
        return self.role == UserRole.ADMIN

    def display_name(self) -> str:
        return self.full_name or (self.email.split("@")[0] if self.email else "Customer")


class Address(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "addresses"
    __table_args__ = (
        Index("ix_addresses_profile_id", "profile_id"),
        # At most one default address per profile. Enforced by the database so
        # two concurrent "set as default" requests cannot both win.
        Index(
            "uq_addresses_one_default_per_profile",
            "profile_id",
            unique=True,
            postgresql_where=text("is_default"),
        ),
    )

    profile_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("profiles.id", ondelete="CASCADE"), nullable=False
    )

    label: Mapped[str] = mapped_column(String(48), nullable=False, server_default="Home")
    address_type: Mapped[AddressType] = mapped_column(
        enum_column(AddressType, "address_type", default=AddressType.SHIPPING),
        nullable=False,
        server_default=AddressType.SHIPPING.value,
    )

    full_name: Mapped[str] = mapped_column(String(160), nullable=False)
    phone: Mapped[str] = mapped_column(String(24), nullable=False)
    line1: Mapped[str] = mapped_column(String(200), nullable=False)
    line2: Mapped[str | None] = mapped_column(String(200))
    landmark: Mapped[str | None] = mapped_column(String(160))
    city: Mapped[str] = mapped_column(String(96), nullable=False)
    state: Mapped[str] = mapped_column(String(96), nullable=False)
    postal_code: Mapped[str] = mapped_column(String(16), nullable=False)
    country_code: Mapped[str] = mapped_column(
        String(2), nullable=False, server_default="IN"
    )

    is_default: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")

    profile: Mapped[Profile] = relationship(back_populates="addresses", lazy="joined")

    def one_line(self) -> str:
        parts = [self.line1]
        if self.line2:
            parts.append(self.line2)
        if self.landmark:
            parts.append(f"near {self.landmark}")
        parts.extend([self.city, self.state, self.postal_code])
        return ", ".join(p for p in parts if p)
