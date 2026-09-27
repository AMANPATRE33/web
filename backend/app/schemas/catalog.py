"""Catalogue response contracts.

These shapes are what the storefront renders from. They are deliberately
*denormalised for display*: a product card carries its price, rating and
availability as plain fields, so the listing page does not need a second
request to know whether an item can be bought.

Everything here is derived server-side from the database. Nothing in this module
is ever populated from a client-supplied value.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.common import Money

ProductSort = Literal[
    "relevance",
    "newest",
    "oldest",
    "price_asc",
    "price_desc",
    "rating",
    "popular",
    "name_asc",
    "name_desc",
]

StockStatus = Literal["in_stock", "low_stock", "out_of_stock", "preorder"]


# ---------------------------------------------------------------------------
# Images
# ---------------------------------------------------------------------------
class ProductImageResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    url: str
    alt_text: str
    position: int
    is_primary: bool
    width: int | None = None
    height: int | None = None
    blur_data_url: str | None = None


# ---------------------------------------------------------------------------
# Variants
# ---------------------------------------------------------------------------
class VariantResponse(BaseModel):
    """A purchasable configuration.

    ``price`` is the *effective* price, already resolved through the variant
    override, so the client never re-implements the inheritance rule.
    """

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    sku: str
    title: str
    attributes: dict[str, str] = Field(default_factory=dict)
    price: Money
    compare_at_price: Money | None = None
    discount_percent: int = 0
    currency: str = "INR"
    status: str
    is_default: bool
    available_quantity: int = 0
    in_stock: bool = True
    low_stock: bool = False
    #: The option axes this variant defines, e.g. {"Colour": "Midnight"}.
    #: The PDP groups these to render the selector controls.
    options: dict[str, str] = Field(default_factory=dict)


class VariantOption(BaseModel):
    """One axis of the variant matrix, e.g. all available Colours."""

    name: str
    values: list[str]
    #: Maps a value to the variant ids that carry it, so a colour can be
    #: disabled when the selected size is out of stock.
    variant_ids_by_value: dict[str, list[uuid.UUID]] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# Products
# ---------------------------------------------------------------------------
class ProductCardResponse(BaseModel):
    """Everything a product card needs, in one object."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title: str
    slug: str
    subtitle: str | None = None
    short_description: str | None = None
    brand: str | None = None
    sku: str
    category_id: uuid.UUID
    category_name: str
    category_slug: str

    price: Money
    compare_at_price: Money | None = None
    discount_percent: int = 0
    is_on_sale: bool = False

    primary_image: ProductImageResponse | None = None
    image_count: int = 0

    rating_average: float = 0.0
    rating_count: int = 0
    is_featured: bool = False
    tags: list[str] = Field(default_factory=list)

    stock_status: StockStatus = "in_stock"
    in_stock: bool = True
    total_available: int = 0
    #: Distinct colours shown as swatches on the card.
    available_colors: list[str] = Field(default_factory=list)

    created_at: datetime | None = None


class ProductDetailResponse(BaseModel):
    """Full product page payload."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title: str
    slug: str
    subtitle: str | None = None
    short_description: str | None = None
    description: str = ""
    sku: str
    brand: str | None = None

    category: CategorySummary
    breadcrumb: list[CategorySummary] = Field(default_factory=list)

    price: Money
    compare_at_price: Money | None = None
    discount_percent: int = 0
    min_price: Money | None = None
    max_price: Money | None = None

    specs: dict[str, str] = Field(default_factory=dict)
    tags: list[str] = Field(default_factory=list)

    images: list[ProductImageResponse] = Field(default_factory=list)
    variants: list[VariantResponse] = Field(default_factory=list)
    options: list[VariantOption] = Field(default_factory=list)

    rating_average: float = 0.0
    rating_count: int = 0
    rating_distribution: dict[str, int] = Field(default_factory=dict)

    is_featured: bool = False
    status: str
    stock_status: StockStatus = "in_stock"
    in_stock: bool = True
    total_available: int = 0

    seo_title: str | None = None
    seo_description: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


# ---------------------------------------------------------------------------
# Categories
# ---------------------------------------------------------------------------
class CategorySummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    slug: str
    parent_id: uuid.UUID | None = None
    image_url: str | None = None
    position: int = 0


class CategoryResponse(CategorySummary):
    description: str | None = None
    seo_title: str | None = None
    seo_description: str | None = None
    #: Direct children, for rendering a category tree.
    children: list[CategorySummary] = Field(default_factory=list)
    #: Ancestors from root to this category, for breadcrumbs.
    ancestors: list[CategorySummary] = Field(default_factory=list)
    product_count: int = 0
    path: str = ""


# ---------------------------------------------------------------------------
# Search
# ---------------------------------------------------------------------------
class SearchSuggestion(BaseModel):
    text: str
    type: Literal["product", "category", "brand", "tag"]
    slug: str | None = None
    product_id: uuid.UUID | None = None


class SearchResultItem(BaseModel):
    """A hit in the search results list."""

    type: Literal["product", "category"]
    id: uuid.UUID
    title: str
    slug: str
    subtitle: str | None = None
    image_url: str | None = None
    price: Money | None = None
    in_stock: bool = True


# ---------------------------------------------------------------------------
# Related / recently viewed
# ---------------------------------------------------------------------------
class RelatedProduct(BaseModel):
    """Compact shape for related and recently-viewed rails.

    Deliberately smaller than ``ProductCardResponse``: these rails render eight
    to twelve small items per page, and the extra fields would be dead weight
    in both the response and the React tree.
    """

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title: str
    slug: str
    brand: str | None = None
    price: Money
    compare_at_price: Money | None = None
    discount_percent: int = 0
    primary_image: ProductImageResponse | None = None
    in_stock: bool = True
    rating_average: float = 0.0
    rating_count: int = 0
    reason: str | None = Field(
        default=None,
        description="Why this is recommended: same_category | same_brand | also_viewed",
    )


# Resolve the forward reference created by the recursive breadcrumb type.
ProductDetailResponse.model_rebuild()
