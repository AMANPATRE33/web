"""SQLAlchemy declarative base, shared column mixins and PostgreSQL enum types.

Design rules enforced here:

* Primary keys are ``uuid`` (Supabase compatible, no sequence enumeration).
* Every mutable row carries ``created_at`` / ``updated_at`` set by the database
  clock, not the application clock, so they cannot drift across regions.
* Money is stored as ``BIGINT`` minor units (paise). Floats are never used.
* PostgreSQL enums are created with explicit values so that adding a variant in
  a future migration is an additive ``ALTER TYPE ... ADD VALUE``.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import ClassVar

from sqlalchemy import DateTime, MetaData, func
from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

# Deterministic constraint naming keeps Alembic autogenerate diffs stable and
# makes down-migrations possible (Alembic can drop a constraint by name).
NAMING_CONVENTION = {
    "ix": "ix_%(table_name)s_%(column_0_N_name)s",
    "uq": "uq_%(table_name)s_%(column_0_N_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)

    type_annotation_map: ClassVar[dict[object, object]] = {
        dict[str, object]: JSONB,
        list[str]: JSONB,
        uuid.UUID: PGUUID(as_uuid=True),
        datetime: DateTime(timezone=True),
    }


# ---------------------------------------------------------------------------
# Column mixins
# ---------------------------------------------------------------------------
class UUIDPrimaryKeyMixin:
    id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


# ---------------------------------------------------------------------------
# Reusable column types
# ---------------------------------------------------------------------------
def enum_column(enum_cls: type[StrEnum], name: str, **kwargs: object) -> SAEnum:
    """Build a native PostgreSQL enum column with a stable type name."""
    return SAEnum(
        enum_cls,
        name=name,
        native_enum=True,
        values_callable=lambda e: [member.value for member in e],
        validate_strings=True,
        **kwargs,  # type: ignore[arg-type]
    )


#: Minor currency units (paise). 100 paise == 1 INR.
MinorUnits = int
Paise = int
Rupees = Decimal
