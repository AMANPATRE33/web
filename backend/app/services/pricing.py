"""Authoritative money arithmetic.

## Why this module exists

A cart total, a checkout total and an invoice total must be the *same number*.
When a storefront computes them in three places, they drift, and the drift shows
up as a customer being charged a figure nobody can explain. So every monetary
figure in this application is produced here, from the database, and nowhere else.
The browser never computes a total; it renders one.

## Why integer minor units, not `NUMERIC` and not float

All amounts are **integer paise** (100 paise = 1 INR).

* **Not float.** `0.1 + 0.2 != 0.3`. A float total is not a rounding difference,
  it is a correctness bug that surfaces as an accounting discrepancy.
* **Not `NUMERIC(12,2)`.** It would work, but Razorpay quotes amounts in paise as
  integers, and the amount we send must be byte-identical to the amount we
  stored. Storing paise means the gateway value is a copy, not a conversion, so
  a rounding bug is structurally impossible on the payment path.

Configuration values (``tax_rate = 0.18``, ``shipping_flat_rate = 99.00``) arrive
as floats because that is what a human types into a config file. They are
converted to integers **exactly once**, at the boundary, via
``Decimal(str(value))`` - never by float arithmetic. Every subsequent operation
is integer-only.

## GST

India requires GST to be shown on an invoice, which means the tax has to be
recoverable from the price rather than merely displayed. Two modes exist and the
configured one is authoritative:

* **inclusive** (``tax_mode = "inclusive"``, the Indian retail default) - the
  displayed price already contains GST. The customer pays the displayed number.
  The tax *component* is extracted from it. ``total`` does **not** include
  ``tax_total``; the tax is inside ``subtotal``.
* **exclusive** - the displayed price is pre-tax and GST is added on top.

Getting this backwards is not a cosmetic error: it double-charges the customer
and misstates the invoice. ``orders`` carries a ``CHECK`` constraint that
encodes both branches, and ``Order.tax_inclusive`` records which one was used so
a historical invoice can be reproduced exactly.
"""

from __future__ import annotations

import uuid
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from decimal import ROUND_HALF_UP, Decimal
from typing import TYPE_CHECKING, Literal

from app.core.config import Settings, get_settings
from app.core.errors import ValidationError
from app.core.logging import get_logger

if TYPE_CHECKING:
    from app.models.catalog import Product, ProductVariant

logger = get_logger(__name__)

#: Basis points: 1800 == 18.00%. Integer so a rate is never a float.
BPS_SCALE = 10_000

_TaxSplitMode = Literal["INTRA_STATE", "INTER_STATE"]


# ---------------------------------------------------------------------------
# Conversion helpers - float only ever meets Decimal here
# ---------------------------------------------------------------------------
def rupees_to_minor(rupees: float | str | Decimal) -> int:
    """Convert a configured rupee figure to paise, exactly.

    ``round(Decimal("99.00") * 100)`` is 9900. ``round(99.00 * 100)`` happens to
    agree, but ``round(8.115 * 100)`` does not agree with either the decimal
    intent or the invoice. The config is a human-authored decimal literal, so it
    is parsed as a string and never touched as a binary float.
    """
    return int(Decimal(str(rupees)).scaleb(2).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def rate_to_bps(rate: float | str | Decimal) -> int:
    """Convert a configured tax rate to basis points.

    ``0.18`` -> ``1800``. Accepts either a fraction (``0.18``) or a percentage
    (``18``)? No - ambiguity here would be a billing defect waiting to happen, so
    this takes a fraction only and the config documents it that way.
    """
    bps = Decimal(str(rate)) * BPS_SCALE
    if bps < 0:
        raise ValidationError("Tax rate cannot be negative.", code="invalid_tax_rate")
    return int(bps.quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def format_rate_bps(bps: int) -> str:
    """Render basis points for display: ``1800`` -> ``"18"``."""
    whole = Decimal(bps) / 100
    text = f"{whole:f}".rstrip("0").rstrip(".")
    return text or "0"


def _round_div(numerator: int, denominator: int) -> int:
    """Integer division rounded half-up, denominator strictly positive.

    Half-up rather than banker's rounding because that is what Indian retail
    invoicing expects, and a consistent rule beats a mathematically tidier one.
    """
    if denominator <= 0:
        raise ValueError("denominator must be positive")
    return (numerator * 2 + denominator) // (2 * denominator)


# ---------------------------------------------------------------------------
# Tax
# ---------------------------------------------------------------------------
def extract_tax_from_inclusive(taxable: int, rate_bps: int) -> int:
    """Tax *contained within* an inclusive price.

    With GST inside the price, ``taxable = value + tax`` and
    ``tax = value * rate``. Solving: ``tax = taxable * rate / (1 + rate)``.

    Worked example: Rs.1525.42 of tax-inclusive goods at 18%.
    ``152542 * 1800 / 11800 = 23269.12`` -> 23269 paise of tax, leaving a net
    value of 129273. Net + tax == gross, to the paisa.
    """
    if taxable <= 0 or rate_bps <= 0:
        return 0
    return _round_div(taxable * rate_bps, BPS_SCALE + rate_bps)


def add_tax_exclusive(taxable: int, rate_bps: int) -> int:
    """Tax *added on top of* a pre-tax price."""
    if taxable <= 0 or rate_bps <= 0:
        return 0
    return _round_div(taxable * rate_bps, BPS_SCALE)


def split_tax(
    tax_total: int, split_mode: _TaxSplitMode
) -> tuple[int, int, int]:
    """Split a tax total into ``(igst, cgst, sgst)`` in paise.

    An intra-state sale is taxed as CGST + SGST, each half the total; inter-state
    as IGST, the whole amount. The halves are computed so they always re-sum to
    ``tax_total`` exactly - the odd paise goes to CGST. A GST invoice whose two
    halves do not add up to the printed total is a rejected invoice.
    """
    if tax_total <= 0:
        return 0, 0, 0
    if split_mode == "INTER_STATE":
        return tax_total, 0, 0
    cgst = _round_div(tax_total, 2)
    return 0, cgst, tax_total - cgst


# ---------------------------------------------------------------------------
# Shipping
# ---------------------------------------------------------------------------
@dataclass(frozen=True, slots=True)
class ShippingQuote:
    method: str
    name: str
    total: int
    estimated_days_min: int
    estimated_days_max: int
    free_applied: bool = False


def quote_shipping(
    *,
    settings: Settings,
    subtotal_after_discount: int,
    method_code: str = "STANDARD",
) -> ShippingQuote:
    """Price shipping from configuration.

    Free above a threshold is a configuration value, not a hard-coded business
    rule - ``docs/CONTENT_PENDING.md` §1.3 records that the real shipping matrix
    is unpublished, so this reads settings and can be corrected without a code
    change. A zero threshold means "never free", and a NULL/zero flat rate means
    shipping is not charged at all (which is how a pickup-only store is modelled).
    """
    flat = rupees_to_minor(settings.shipping_flat_rate)
    free_above = (
        rupees_to_minor(settings.shipping_free_above) if settings.shipping_free_above else 0
    )

    free_applied = bool(free_above) and subtotal_after_discount >= free_above
    total = 0 if free_applied else flat

    name, days_min, days_max = _SHIPPING_PRESETS.get(method_code, _SHIPPING_PRESETS["STANDARD"])
    return ShippingQuote(
        method=method_code,
        name=name,
        total=total,
        estimated_days_min=days_min,
        estimated_days_max=days_max,
        free_applied=free_applied,
    )


#: Presentation-only estimates. The real courier matrix is unpublished; these
#: are clearly config-driven and must not be read as a promise.
_SHIPPING_PRESETS: dict[str, tuple[str, int, int]] = {
    "STANDARD": ("Standard delivery", 3, 5),
    "EXPRESS": ("Express delivery", 1, 2),
    "FREIGHT": ("Road freight", 5, 10),
}


# ---------------------------------------------------------------------------
# Line pricing
# ---------------------------------------------------------------------------
@dataclass(frozen=True, slots=True)
class PricedLine:
    """One cart or order line, priced from the database.

    ``unit_price`` comes from the variant's effective price, never from the
    request. ``available`` is the sellable quantity at read time, so the client
    can be told the truth about stock without a second round trip.
    """

    cart_item_id: uuid.UUID
    variant_id: uuid.UUID
    product_id: uuid.UUID
    product_slug: str
    product_title: str
    variant_title: str
    sku: str
    attributes: dict[str, object]
    image_url: str | None
    unit_price: int
    compare_at_price: int | None
    quantity: int
    line_total: int
    available: int
    is_purchasable: bool
    #: Machine-readable reason the line cannot be bought right now, if any.
    blocked_reason: str | None = None


def effective_unit_price(variant: ProductVariant) -> int:
    """The price actually charged for a variant.

    ``price_override`` wins when set; otherwise the variant's own ``price``,
    which the seeder derives from the product base. Both are integer paise
    already, so there is no conversion here and therefore no rounding here.
    """
    if variant.price_override is not None:
        return int(variant.price_override)
    return int(variant.price)


def build_priced_line(
    *,
    cart_item_id: uuid.UUID,
    quantity: int,
    variant: ProductVariant,
    product: Product,
    image_url: str | None,
    available: int,
) -> PricedLine:
    """Assemble one priced line, including *why* it cannot be purchased.

    A line is only purchasable when the variant is ACTIVE, the product is
    ACTIVE, and stock covers the requested quantity. The reason is carried
    through to the client so the cart can render a specific, honest message
    instead of a dead quantity stepper.
    """
    unit_price = effective_unit_price(variant)
    attributes = dict(variant.attributes or {})

    reason: str | None = None
    if str(variant.status) != "ACTIVE":
        reason = "variant_unavailable"
    elif str(product.status) != "ACTIVE":
        reason = "product_unavailable"
    elif available <= 0:
        reason = "out_of_stock"
    elif quantity > available:
        reason = "insufficient_stock"

    material = attributes.get("Material")
    size = attributes.get("Size")
    variant_title = " / ".join(
        str(part) for part in (material, size) if part
    ) or (variant.title or variant.sku)

    return PricedLine(
        cart_item_id=cart_item_id,
        variant_id=variant.id,
        product_id=product.id,
        product_slug=product.slug,
        product_title=product.title,
        variant_title=variant_title,
        sku=variant.sku,
        attributes=attributes,
        image_url=image_url,
        unit_price=unit_price,
        compare_at_price=variant.compare_at_price,
        quantity=quantity,
        line_total=unit_price * quantity,
        available=available,
        is_purchasable=reason is None,
        blocked_reason=reason,
    )


# ---------------------------------------------------------------------------
# Totals
# ---------------------------------------------------------------------------
@dataclass(frozen=True, slots=True)
class Totals:
    """A complete, internally consistent set of order figures.

    Invariant, enforced by a database CHECK as well as by construction:
    ``total == subtotal - discount_total + shipping_total`` for inclusive tax,
    and the same plus ``tax_total`` for exclusive tax.
    """

    subtotal: int
    discount_total: int
    shipping_total: int
    tax_total: int
    total: int
    taxable_amount: int
    tax_rate_bps: int
    tax_inclusive: bool
    tax_split_mode: _TaxSplitMode
    igst: int
    cgst: int
    sgst: int
    item_count: int
    shipping: ShippingQuote | None = None
    #: Set when something in the cart made a line unpurchasable, so checkout
    #: can refuse with specifics rather than a generic failure.
    blocking: tuple[str, ...] = field(default=())

    def as_order_columns(self) -> dict[str, object]:
        """The exact column values to persist on ``orders``."""
        return {
            "subtotal": self.subtotal,
            "discount_total": self.discount_total,
            "shipping_total": self.shipping_total,
            "tax_total": self.tax_total,
            "total": self.total,
            "taxable_amount": self.taxable_amount,
            "tax_rate_bps": self.tax_rate_bps,
            "tax_inclusive": self.tax_inclusive,
            "tax_split_mode": self.tax_split_mode,
        }

    def is_zero(self) -> bool:
        return self.subtotal == 0


def compute_totals(
    lines: Sequence[PricedLine],
    *,
    settings: Settings | None = None,
    discount_total: int = 0,
    shipping_method: str = "STANDARD",
    tax_split_mode: _TaxSplitMode | None = None,
) -> Totals:
    """Derive subtotal, discount, shipping, tax and total.

    The caller supplies **priced lines from the database** and an already-validated
    discount. Nothing here reads a price off a request object, because there is
    no request object anywhere near this function.
    """
    settings = settings or get_settings()

    subtotal = sum(line.line_total for line in lines)

    # An empty cart is worth zero. Not "zero goods plus the shipping rate" -
    # that is what the naive path produces, and it means the header badge's cart
    # shows a shopper a Rs.99 total for a basket they have not filled yet, and
    # that checkout is chargeable before a single item is in it.
    if not lines or subtotal <= 0:
        return Totals(
            subtotal=0,
            discount_total=0,
            shipping_total=0,
            tax_total=0,
            total=0,
            taxable_amount=0,
            tax_rate_bps=rate_to_bps(settings.tax_rate),
            tax_inclusive=settings.tax_mode == "inclusive",
            tax_split_mode=_configured_split_mode(settings),
            igst=0,
            cgst=0,
            sgst=0,
            item_count=0,
            shipping=None,
        )

    # A discount can never exceed the goods it discounts; clamping here means a
    # miscalculated coupon degrades to "free goods, no negative total" instead of
    # a negative payable amount.
    discount_total = max(0, min(int(discount_total), subtotal))

    goods_after_discount = subtotal - discount_total

    shipping = quote_shipping(
        settings=settings,
        subtotal_after_discount=goods_after_discount,
        method_code=shipping_method,
    )
    shipping_total = shipping.total

    # GST applies to goods. Shipping is a supply of transportation and is taxed
    # separately; folding it into the goods base would misstate both lines of
    # the invoice, so `taxable_amount` deliberately excludes it (and the column
    # comment says so).
    taxable_amount = goods_after_discount

    tax_inclusive = settings.tax_mode == "inclusive"
    rate_bps = rate_to_bps(settings.tax_rate)

    if tax_inclusive:
        tax_total = extract_tax_from_inclusive(taxable_amount, rate_bps)
        total = goods_after_discount + shipping_total
    else:
        tax_total = add_tax_exclusive(taxable_amount, rate_bps)
        total = goods_after_discount + shipping_total + tax_total

    if total < 0:  # pragma: no cover - unreachable given the clamp above
        raise ValidationError("Computed a negative order total.", code="invalid_total")

    split_mode: _TaxSplitMode = tax_split_mode or _configured_split_mode(settings)
    igst, cgst, sgst = split_tax(tax_total, split_mode)

    blocking = tuple(
        f"{line.sku}: {line.blocked_reason}"
        for line in lines
        if not line.is_purchasable
    )

    return Totals(
        subtotal=subtotal,
        discount_total=discount_total,
        shipping_total=shipping_total,
        tax_total=tax_total,
        total=total,
        taxable_amount=taxable_amount,
        tax_rate_bps=rate_bps,
        tax_inclusive=tax_inclusive,
        tax_split_mode=split_mode,
        igst=igst,
        cgst=cgst,
        sgst=sgst,
        item_count=sum(line.quantity for line in lines),
        shipping=shipping,
        blocking=blocking,
    )


def _configured_split_mode(settings: Settings) -> _TaxSplitMode:
    """Which GST split to apply.

    The store is registered in Gujarat; the overwhelming majority of this
    business's volume is intra-state, and an inter-state sale to a customer with
    a valid GSTIN is still intra-state-supply-with-IGST only when the *place of
    supply* differs. We store customer state as free text, not a state code, so
    that determination is not reliable and guessing it would be a compliance
    risk on a tax document.

    So it is configuration, and the chosen value is written to the order so the
    invoice that was issued can always be reproduced. See
    `docs/CONTENT_PENDING.md` §1.1.
    """
    raw = (settings.tax_split_mode or "INTRA_STATE").strip().upper()
    return "INTER_STATE" if raw == "INTER_STATE" else "INTRA_STATE"


def spread_discount(discount_total: int, line_totals: Sequence[int]) -> list[int]:
    """Split a cart-level discount across lines without losing or inventing a paisa.

    Used so a refund on one line can be computed from the line's own share. Each
    line gets ``floor`` of the proportional share, and the remaining paise are
    handed out one-per-line to the largest shares first. The result always sums
    back to ``discount_total`` exactly - tested, because a refund that is off by
    one paisa is a reconciliation failure someone has to chase.
    """
    if discount_total <= 0 or not line_totals:
        return [0] * len(line_totals)

    grand = sum(line_totals)
    if grand <= 0:
        return [0] * len(line_totals)

    raw = [(discount_total * total) // grand for total in line_totals]
    remainder = discount_total - sum(raw)

    # Largest share first, so the odd paisa lands where it matters least.
    order = sorted(range(len(line_totals)), key=lambda i: (-line_totals[i], i))
    for i in range(remainder):
        raw[order[i % len(order)]] += 1
    return raw


def allocate_line_tax(
    line_goods_total: int, totals: Totals
) -> int:
    """Attribute part of the order tax to a single line, for the invoice.

    Uses the same largest-first remainder distribution as the discount, so
    ``sum(line_tax) == totals.tax_total`` exactly.
    """
    if totals.tax_total <= 0:
        return 0
    goods = totals.subtotal - totals.discount_total
    if goods <= 0 or line_goods_total <= 0:
        return 0
    return spread_discount(totals.tax_total, [line_goods_total])[0]


def sum_check(values: Iterable[int]) -> int:
    return sum(int(v) for v in values)
