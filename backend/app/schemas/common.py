"""Shared response contracts: pagination, money, enums.

Money is integer **minor units** (paise) everywhere on the wire. A float is
never used, because 0.1 + 0.2 != 0.3 and a storefront that gets this wrong
loses money on every order. The frontend formats minor units for display using
the same integer arithmetic.
"""

from __future__ import annotations

import math
from typing import Annotated, Generic, TypeVar

from pydantic import BaseModel, ConfigDict, Field

T = TypeVar("T")

#: Minor units. 100 paise == 1 INR.
Minor = Annotated[int, Field(ge=0, description="Amount in minor units (paise)")]


class PaginationParams(BaseModel):
    """Validated ``?page=&per_page=`` query parameters."""

    page: int = Field(default=1, ge=1, le=10_000)
    per_page: int = Field(default=24, ge=1, le=100)

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.per_page

    @property
    def limit(self) -> int:
        return self.per_page


class PageMeta(BaseModel):
    page: int
    per_page: int
    total: int
    total_pages: int
    has_next: bool
    has_previous: bool

    @classmethod
    def build(cls, *, page: int, per_page: int, total: int) -> PageMeta:
        total_pages = math.ceil(total / per_page) if per_page else 0
        return cls(
            page=page,
            per_page=per_page,
            total=total,
            total_pages=total_pages,
            has_next=page < total_pages,
            has_previous=page > 1 and total > 0,
        )


class Page(BaseModel, Generic[T]):
    """A paginated collection. ``items`` is always a list, never null."""

    model_config = ConfigDict(populate_by_name=True)

    items: list[T]
    meta: PageMeta


class Money(BaseModel):
    """Amount plus display context.

    ``amount`` is the authoritative value. ``formatted`` and ``symbol`` exist so
    the client never has to reimplement currency formatting - and never has the
    opportunity to format it differently on the server and the client.
    """

    amount: Minor
    currency: str = "INR"
    symbol: str = "Rs."
    formatted: str = ""

    @classmethod
    def build(cls, amount: int, *, currency: str = "INR", symbol: str = "Rs.") -> Money:
        return cls(
            amount=amount,
            currency=currency,
            symbol=symbol,
            formatted=format_minor(amount, symbol=symbol),
        )


def _group_indian(digits: str) -> str:
    """Group an integer digit string using the Indian lakh/crore convention.

    ``1234567`` becomes ``12,34,567`` - groups of two from the right after the
    first group of three, not the western ``1,234,567``. Getting this wrong on a
    price is the kind of detail a customer notices immediately.
    """
    if len(digits) <= 3:
        return digits

    head, tail = digits[:-3], digits[-3:]
    if len(head) <= 2:
        return f"{head},{tail}"

    groups: list[str] = []
    while len(head) > 2:
        groups.insert(0, head[-2:])
        head = head[:-2]
    groups.insert(0, head)
    return ",".join([*groups, tail])


def format_minor(amount: int, *, symbol: str = "Rs.") -> str:
    """Render minor units for display, using integer arithmetic only.

    A trailing ``.00`` is omitted: on a retail price it is noise, and the
    fractional part only appears when there genuinely is one.
    """
    sign = "-" if amount < 0 else ""
    value = abs(int(amount))
    rupees, paise = divmod(value, 100)

    whole = _group_indian(f"{rupees:,}".replace(",", ""))
    if paise:
        return f"{sign}{symbol}{whole}.{paise:02d}"
    return f"{sign}{symbol}{whole}"


class SortDirection(str):
    ASC = "asc"
    DESC = "desc"
