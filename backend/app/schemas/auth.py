"""Pydantic contracts for the auth surface.

Note what is *absent*: there is no ``LoginRequest.password`` flow that posts a
password to this API. Sign-in, sign-up and password reset are handled directly
by Supabase Auth from the browser over TLS, so plaintext passwords never reach
an application server, are never logged, and are never stored by us.

These schemas cover the two things the API genuinely owns: reporting the
current session's identity and role, and server-side administrative user
management.
"""

from __future__ import annotations

import re
import uuid
from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

# Slightly conservative: rejects the addresses that actually fail delivery
# rather than trying to be a complete RFC 5322 parser.
EMAIL_PATTERN = re.compile(r"^[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}$")

PHONE_PATTERN = re.compile(r"^[+]?[0-9][0-9\s\-]{7,17}$")

Password = Annotated[
    str,
    Field(
        min_length=10,
        max_length=128,
        description=(
            "At least 10 characters. Length matters more than symbol classes; "
            "composition rules push people towards predictable substitutions."
        ),
    ),
]


def normalise_email(value: str) -> str:
    return value.strip().lower()


def normalise_phone(value: str) -> str:
    return re.sub(r"[\s\-]", "", value.strip())


class ApiModel(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")


# ---------------------------------------------------------------------------
# Session
# ---------------------------------------------------------------------------
class SessionUser(BaseModel):
    """Who the caller is, as the API understands them."""

    id: uuid.UUID
    email: EmailStr
    full_name: str | None = None
    phone: str | None = None
    role: Literal["CUSTOMER", "ADMIN"]
    is_admin: bool
    email_verified: bool = False
    created_at: datetime | None = None

    @property
    def display_name(self) -> str:
        return self.full_name or self.email.split("@")[0]


class SessionResponse(ApiModel):
    user: SessionUser
    #: Roles the *token* claims. Shown for debugging only; the API authorises
    #: on ``user.role``, which comes from the database.
    token_roles: list[str] = Field(default_factory=list)


class ProfileUpdateRequest(ApiModel):
    full_name: str | None = Field(default=None, min_length=1, max_length=160)
    phone: str | None = Field(default=None, max_length=24)
    marketing_opt_in: bool | None = None

    @field_validator("phone")
    @classmethod
    def _check_phone(cls, value: str | None) -> str | None:
        if value is None or value == "":
            return None
        if not PHONE_PATTERN.match(value):
            raise ValueError("Enter a valid phone number, e.g. +91 98765 43210")
        return normalise_phone(value)

    @field_validator("full_name")
    @classmethod
    def _check_name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip()
        return cleaned or None


# ---------------------------------------------------------------------------
# Address book
# ---------------------------------------------------------------------------
class AddressCreateRequest(ApiModel):
    label: str = Field(default="Home", min_length=1, max_length=48)
    full_name: str = Field(min_length=2, max_length=160)
    phone: str = Field(min_length=7, max_length=24)
    line1: str = Field(min_length=3, max_length=200)
    line2: str | None = Field(default=None, max_length=200)
    landmark: str | None = Field(default=None, max_length=160)
    city: str = Field(min_length=2, max_length=96)
    state: str = Field(min_length=2, max_length=96)
    postal_code: str = Field(min_length=3, max_length=16)
    country_code: str = Field(default="IN", min_length=2, max_length=2)
    is_default: bool = False

    @field_validator("country_code")
    @classmethod
    def _upper_country(cls, value: str) -> str:
        return value.upper()

    @field_validator("phone")
    @classmethod
    def _check_phone(cls, value: str) -> str:
        if not PHONE_PATTERN.match(value):
            raise ValueError("Enter a valid phone number, e.g. +91 98765 43210")
        return normalise_phone(value)

    @field_validator("postal_code")
    @classmethod
    def _check_postal(cls, value: str) -> str:
        cleaned = value.strip()
        if not re.match(r"^[A-Za-z0-9][A-Za-z0-9\- ]{1,14}$", cleaned):
            raise ValueError("Enter a valid postal code")
        return cleaned


class AddressUpdateRequest(ApiModel):
    label: str | None = Field(default=None, min_length=1, max_length=48)
    full_name: str | None = Field(default=None, min_length=2, max_length=160)
    phone: str | None = Field(default=None, min_length=7, max_length=24)
    line1: str | None = Field(default=None, min_length=3, max_length=200)
    line2: str | None = Field(default=None, max_length=200)
    landmark: str | None = Field(default=None, max_length=160)
    city: str | None = Field(default=None, min_length=2, max_length=96)
    state: str | None = Field(default=None, min_length=2, max_length=96)
    postal_code: str | None = Field(default=None, min_length=3, max_length=16)
    country_code: str | None = Field(default=None, min_length=2, max_length=2)
    is_default: bool | None = None

    _check_phone = field_validator("phone")(AddressCreateRequest._check_phone.__func__)  # type: ignore[attr-defined]
    _upper_country = field_validator("country_code")(
        AddressCreateRequest._upper_country.__func__  # type: ignore[attr-defined]
    )
    _check_postal = field_validator("postal_code")(
        AddressCreateRequest._check_postal.__func__  # type: ignore[attr-defined]
    )


class AddressResponse(ApiModel):
    id: uuid.UUID
    label: str
    full_name: str
    phone: str
    line1: str
    line2: str | None = None
    landmark: str | None = None
    city: str
    state: str
    postal_code: str
    country_code: str
    is_default: bool
    created_at: datetime
    updated_at: datetime
    one_line: str


# ---------------------------------------------------------------------------
# Admin user management
# ---------------------------------------------------------------------------
class AdminCreateUserRequest(ApiModel):
    """Server-side account creation, e.g. for support-assisted signup."""

    email: EmailStr
    password: Password
    email_confirm: bool = True
    full_name: str | None = Field(default=None, max_length=160)
    phone: str | None = Field(default=None, max_length=24)
    role: Literal["CUSTOMER", "ADMIN"] = "CUSTOMER"


class AdminUserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: str
    full_name: str | None = None
    phone: str | None = None
    role: str
    is_active: bool
    email_verified: bool = False
    created_at: datetime | None = None
    last_login_at: datetime | None = None


class AdminRoleUpdateRequest(ApiModel):
    role: Literal["CUSTOMER", "ADMIN"]


class AdminUserListResponse(ApiModel):
    items: list[AdminUserResponse]
    total: int
    page: int
    per_page: int


class PasswordResetAdminRequest(ApiModel):
    """Trigger a Supabase recovery email on a user's behalf."""

    email: EmailStr
    redirect_to: str | None = None
