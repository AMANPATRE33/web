"""Request and response contracts for cart, checkout, orders and payments.

## What a request is allowed to contain

A cart write carries a **variant id and a quantity. Nothing else.**

No price, no title, no SKU, no stock level, no product name. Those are all
resolved from the database on read, in `services.cart.price_cart`. This is not
fastidiousness for its own sake: every one of those fields, if accepted from a
client, is a field an attacker can set. A `price` on the request body would
either be ignored (harmless, but a trap for the next developer) or trusted (a
cart that costs nothing).

The only other field accepted is `added_from`, a short non-price hint used to
explain cart contents in a support ticket ("added from the product page").

## Response shape

`CartResponse` returns a fully-resolved view: for each line, the product, the
variant, the material, the size, the price and the current stock, all read from
the database at that moment. `totals` is computed by `services.pricing` and is
authoritative. The `is_estimate` flag exists because the storefront historically
computed totals in the browser; it is `True` only while that path is still
reachable, so a client cannot mistake a browser-derived figure for a settled one.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator, model_validator

from app.schemas.common import Money

#: A quantity. 1..99 matches the `cart_items` CHECK constraints, so validation
#: and the database agree and neither can be the weaker one.
CartQuantity = Annotated[int, Field(ge=1, le=99, description="Units to order (1-99)")]

PhoneNumber = Annotated[
    str,
    Field(
        min_length=10,
        max_length=15,
        pattern=r"^[0-9]{10}$|^[0-9]{2}[0-9]{10}$|^[0-9]{3}[0-9]{10}$|^[0-9]{3}[0-9]{3}[0-9]{4}$",
        description="10 to 15 digits, optionally with a country code",
    ),
]

PostalCode = Annotated[
    str,
    Field(min_length=6, max_length=10, pattern=r"^[0-9]{6}$|^[0-9]{5}$|^[A-Za-z0-9 -]{4,10}$"),
]


# ---------------------------------------------------------------------------
# Cart
# ---------------------------------------------------------------------------
class CartItemAddRequest(BaseModel):
    """Add a variant to the cart.

    Deliberately minimal. See the module docstring.
    """

    model_config = ConfigDict(extra="forbid")

    variant_id: uuid.UUID
    quantity: CartQuantity = 1
    #: Non-price hint, e.g. "product_page" or "cart_reorder". Never displayed
    #: as authoritative and never used in a calculation.
    added_from: Annotated[str, Field(max_length=64)] | None = None


class CartItemUpdateRequest(BaseModel):
    """Change the quantity of an existing line. Absolute, not a delta.

    An absolute quantity makes a retry idempotent: sending \`{quantity: 2}\` twice
    leaves 2 units, whereas a delta would give 4.
    """

    model_config = ConfigDict(extra="forbid")

    quantity: CartQuantity


class CartLineResponse(BaseModel):
    """One resolved cart line. Every field comes from the database."""

    id: uuid.UUID
    variant_id: uuid.UUID
    product_id: uuid.UUID
    product_slug: str
    product_title: str
    variant_title: str
    sku: str
    material: str | None = None
    size: str | None = None
    image_url: str | None = None
    unit_price: Money
    compare_at_price: Money | None = None
    line_total: Money
    quantity: int
    available: int
    is_purchasable: bool = True
    #: Machine-readable, e.g. \`out_of_stock\`. The client maps this to prose.
    blocked_reason: str | None = None
    #: True when the price moved since this line was added. Drives the
    #: "price changed" disclosure at checkout rather than a silent reprice.
    price_changed: bool = False


class CartTotalsResponse(BaseModel):
    subtotal: Money
    discount: Money
    shipping: Money
    tax: Money
    total: Money
    item_count: int
    #: True while any total is computed outside a settled order. See §13 of the
    #: QA report: the browser used to compute these, and the type keeps a
    #: browser-derived figure from being presented as final.
    is_estimate: bool = True
    tax_rate: str = "18"
    tax_inclusive: bool = True
    #: CGST/SGST or IGST, as they will appear on the invoice.
    igst: Money
    cgst: Money
    sgst: Money
    free_shipping_applied: bool = False
    shipping_estimate_days_min: int | None = None
    shipping_estimate_days_max: int | None = None


class CartResponse(BaseModel):
    id: uuid.UUID
    #: \`guest\` or \`account\`, so the client knows whether this cart survives a
    #: sign-out and whether to prompt for sign-in before checkout.
    owner: Literal["guest", "account"]
    status: str
    lines: list[CartLineResponse]
    totals: CartTotalsResponse
    #: Present when some line cannot be bought. Checkout refuses while this is
    #: non-empty, and says which SKU and why.
    blocking: list[str] = Field(default_factory=list)
    updated_at: datetime | None = None


class CartMergeResponse(BaseModel):
    """Result of folding a guest cart into an account cart on sign-in."""

    cart: CartResponse
    #: Variants that appeared in both carts and were merged into one line.
    merged_variants: list[uuid.UUID] = Field(default_factory=list)
    #: Lines dropped because the merged quantity exceeded available stock, with
    #: the quantity that was actually kept. A merge must never silently
    #: over-allocate.
    adjusted: list[CartAdjustment] = Field(default_factory=list)


class CartAdjustment(BaseModel):
    variant_id: uuid.UUID
    sku: str
    requested: int
    kept: int
    reason: str


# ---------------------------------------------------------------------------
# Checkout
# ---------------------------------------------------------------------------
class ShippingAddress(BaseModel):
    model_config = ConfigDict(extra="forbid")

    full_name: Annotated[str, Field(min_length=2, max_length=160)]
    line1: Annotated[str, Field(min_length=3, max_length=200)]
    line2: Annotated[str, Field(max_length=200)] | None = None
    landmark: Annotated[str, Field(max_length=160)] | None = None
    city: Annotated[str, Field(min_length=2, max_length=96)]
    state: Annotated[str, Field(min_length=2, max_length=96)]
    postal_code: PostalCode
    country_code: Annotated[str, Field(min_length=2, max_length=2, pattern=r"^[A-Za-z]{2}$")] = "IN"

    @field_validator("country_code")
    @classmethod
    def _upper(cls, value: str) -> str:
        return value.upper()

    @field_validator("line1", "city", "state", "full_name")
    @classmethod
    def _strip(cls, value: str) -> str:
        return " ".join(value.split())


#: The GSTIN shape: 2-digit state code, 5 letters, 4 digits, 1 letter, "Z",
#: 1 alphanumeric. Enforced here *and* by a database CHECK on `orders.gstin`, so
#: a malformed value cannot reach an issued invoice whatever the caller does.
GstinPattern = r"^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z][0-9A-Z]Z[0-9A-Z]$"


class BusinessDetails(BaseModel):
    """Optional B2B fields. All optional - a consumer order sends none."""

    model_config = ConfigDict(extra="forbid")

    is_business_order: bool = False
    company_name: Annotated[str, Field(min_length=2, max_length=200)] | None = None
    gstin: Annotated[str, Field(pattern=GstinPattern, min_length=15, max_length=15)] | None = None
    purchase_order_number: Annotated[str, Field(max_length=64)] | None = None

    @field_validator("gstin")
    @classmethod
    def _upper_gstin(cls, value: str | None) -> str | None:
        return value.upper() if value else None

    @model_validator(mode="after")
    def _business_needs_a_company(self) -> BusinessDetails:
        # Mirrors the `business_order_needs_company` CHECK on `orders`. A GST
        # invoice addressed to nobody is not an invoice.
        if self.is_business_order and not self.company_name:
            raise ValueError("A business order needs a company name to invoice to.")
        return self


class CheckoutRequest(BaseModel):
    """Place an order.

    Contains no totals. The server recomputes every figure from the cart and the
    catalogue, and a client that sends a total is not believed.
    """

    model_config = ConfigDict(extra="forbid")

    contact_name: Annotated[str, Field(min_length=2, max_length=160)]
    email: EmailStr
    phone: PhoneNumber

    shipping: ShippingAddress
    business: BusinessDetails = Field(default_factory=BusinessDetails)

    shipping_method: Literal["STANDARD", "EXPRESS", "FREIGHT"] = "STANDARD"
    customer_note: Annotated[str, Field(max_length=500)] | None = None

    #: Reuse a saved address by id instead of resending it. Scoped to the
    #: caller: an address id belonging to another customer is simply not found.
    saved_address_id: uuid.UUID | None = None

    @field_validator("contact_name", "customer_note")
    @classmethod
    def _strip(cls, value: str | None) -> str | None:
        return " ".join(value.split()) if value else value


class CheckoutQuote(BaseModel):
    """Authoritative totals, returned before any payment is created.

    The checkout page renders this. It is produced by the same function that
    writes `orders`, so what the customer approves and what they are charged are
    computed once.
    """

    subtotal: Money
    discount: Money
    shipping: Money
    tax: Money
    total: Money
    taxable_amount: Money
    tax_rate: str
    tax_inclusive: bool
    igst: Money
    cgst: Money
    sgst: Money
    item_count: int
    free_shipping_applied: bool = False
    lines: list[CartLineResponse]
    blocking: list[str] = Field(default_factory=list)
    #: Configured but unpublished business data the checkout page should surface
    #: rather than paper over. See docs/CONTENT_PENDING.md.
    warnings: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Orders
# ---------------------------------------------------------------------------
class OrderLineResponse(BaseModel):
    id: uuid.UUID
    title: str
    variant_title: str
    sku: str
    slug: str
    image_url: str | None = None
    material: str | None = None
    size: str | None = None
    unit_price: Money
    quantity: int
    line_discount: Money
    line_tax: Money
    total: Money
    #: Stock already returned against this line, for a partial refund view.
    refunded_quantity: int = 0


class OrderEventResponse(BaseModel):
    status: str
    note: str | None = None
    at: datetime


class PaymentResponse(BaseModel):
    id: uuid.UUID
    provider: str
    status: str
    amount: Money
    method: str | None = None
    bank: str | None = None
    razorpay_payment_id: str | None = None
    created_at: datetime
    captured_at: datetime | None = None
    failure_reason: str | None = None


class OrderTotalsResponse(BaseModel):
    subtotal: Money
    discount: Money
    shipping: Money
    tax: Money
    total: Money
    refunded: Money
    currency: str = "INR"


class OrderResponse(BaseModel):
    """A placed order.

    Deliberately excludes `internal_note` - staff-only text must never reach a
    customer endpoint, and the easiest way to guarantee that is for the response
    model to have no field to put it in.
    """

    id: uuid.UUID
    order_number: str
    status: str
    payment_status: str
    placed_at: datetime | None = None
    paid_at: datetime | None = None
    shipped_at: datetime | None = None
    delivered_at: datetime | None = None
    cancelled_at: datetime | None = None

    email: str
    phone: str
    shipping_name: str
    shipping_line1: str
    shipping_line2: str | None = None
    shipping_landmark: str | None = None
    shipping_city: str
    shipping_state: str
    shipping_postal_code: str
    shipping_country_code: str

    is_business_order: bool = False
    company_name: str | None = None
    gstin: str | None = None
    purchase_order_number: str | None = None

    totals: OrderTotalsResponse
    lines: list[OrderLineResponse]
    events: list[OrderEventResponse] = Field(default_factory=list)
    payments: list[PaymentResponse] = Field(default_factory=list)

    invoice_number: str | None = None
    shipping_method: str = "STANDARD"
    tracking_number: str | None = None
    tracking_url: str | None = None
    estimated_delivery: datetime | None = None

    #: Support contact, from verified configuration. Never invented.
    support_email: str
    support_phone: str


class OrderSummaryResponse(BaseModel):
    """Row shape for the order-history list. Cheaper than a full `OrderResponse`
    and the reason the list endpoint does not build a timeline per row."""

    id: uuid.UUID
    order_number: str
    status: str
    payment_status: str
    placed_at: datetime | None = None
    total: Money
    item_count: int
    first_item_title: str | None = None
    cover_image_url: str | None = None


# ---------------------------------------------------------------------------
# Payments
# ---------------------------------------------------------------------------
class PaymentIntentRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    #: Must match the order this intent is for. Checked server-side against the
    #: order the token authorises, so a mismatched pair is a 404 not a payment
    #: against someone else's order.
    order_id: uuid.UUID


class PaymentIntentResponse(BaseModel):
    order_id: uuid.UUID
    order_number: str
    #: The Razorpay **public** key id. The key secret and webhook secret are
    #: backend-only and never appear in any response.
    razorpay_key_id: str
    razorpay_order_id: str
    amount: Money
    currency: str
    #: Exactly the amount the server expects, in the units the gateway wants.
    amount_minor: int
    prefill: PaymentPrefill
    #: Present only when the store is in test mode, so the UI can label it.
    test_mode: bool
    #: Set when payment is unavailable; the UI then explains why instead of
    #: offering a button that cannot work.
    unavailable_reason: str | None = None


class PaymentPrefill(BaseModel):
    name: str
    email: EmailStr
    phone: str


class PaymentVerifyRequest(BaseModel):
    """Client-side verification, submitted after Razorpay's checkout returns.

    This is an **optimisation**, not the authority. The customer reaches their
    confirmation page faster, but a forged or tampered body changes nothing: the
    signature is recomputed against the key secret, and the amount is re-read
    from the order row. The webhook is what actually settles an order.
    """

    model_config = ConfigDict(extra="forbid")

    order_id: uuid.UUID
    razorpay_order_id: str
    razorpay_payment_id: str
    razorpay_signature: str


class PaymentResultResponse(BaseModel):
    order_id: uuid.UUID
    order_number: str
    status: str
    payment_status: str
    #: Where the client should send the customer next.
    redirect_to: str
    verified: bool
