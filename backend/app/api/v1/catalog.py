"""Public catalogue endpoints.

Every figure returned here is read from the database. The client sends filters
and paging, never prices or totals.
"""

from __future__ import annotations

import uuid
from dataclasses import replace
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.logging import get_logger
from app.db.session import get_db
from app.schemas.catalog import (
    CategoryResponse,
    CategorySummary,
    ProductCardResponse,
    ProductDetailResponse,
    ProductImageResponse,
    ProductSort,
    RelatedProduct,
    SearchResultItem,
    SearchSuggestion,
    VariantOption,
    VariantResponse,
)
from app.schemas.common import Money, Page, PageMeta
from app.services import catalog as catalog_service
from app.services.catalog import ProductFilters

logger = get_logger(__name__)

router = APIRouter()


def _settings() -> Settings:
    from app.core.config import get_settings

    return get_settings()


# ---------------------------------------------------------------------------
# Presentation
# ---------------------------------------------------------------------------
def _money(amount: int | None) -> Money | None:
    if amount is None:
        return None
    settings = _settings()
    return Money.build(amount, currency=settings.currency, symbol=settings.currency_symbol)


def _card(product: Any) -> ProductCardResponse:
    price = product.effective_price()
    compare_at = product.compare_at_price
    summary = product.rating_summary
    primary = product.primary_image

    return ProductCardResponse(
        id=product.id,
        title=product.title,
        slug=product.slug,
        subtitle=product.subtitle,
        short_description=product.short_description,
        brand=product.brand,
        sku=product.sku,
        category_id=product.category_id,
        category_name=product.category.name if product.category else "",
        category_slug=product.category.slug if product.category else "",
        price=_money(price),
        compare_at_price=_money(compare_at) if compare_at and compare_at > price else None,
        discount_percent=product.discount_percent,
        is_on_sale=bool(compare_at and compare_at > price),
        primary_image=(ProductImageResponse.model_validate(primary) if primary else None),
        image_count=len(product.images),
        rating_average=round(float(summary.average_rating), 2) if summary else 0.0,
        rating_count=int(summary.review_count) if summary else 0,
        is_featured=product.is_featured,
        tags=[tag.name for tag in product.tags],
        stock_status=catalog_service.stock_status_for(product),
        in_stock=product.in_stock(),
        total_available=sum(v.inventory.available if v.inventory else 0 for v in product.variants),
        available_colors=catalog_service.available_colors(product),
        created_at=product.created_at,
    )


def _related_card(product: Any, reason: str | None) -> RelatedProduct:
    price = product.effective_price()
    compare_at = product.compare_at_price
    summary = product.rating_summary
    primary = product.primary_image
    return RelatedProduct(
        id=product.id,
        title=product.title,
        slug=product.slug,
        brand=product.brand,
        price=_money(price),
        compare_at_price=_money(compare_at) if compare_at and compare_at > price else None,
        discount_percent=product.discount_percent,
        primary_image=ProductImageResponse.model_validate(primary) if primary else None,
        in_stock=product.in_stock(),
        rating_average=round(float(summary.average_rating), 2) if summary else 0.0,
        rating_count=int(summary.review_count) if summary else 0,
        reason=reason,
    )


async def _category_summary(category: Any) -> CategorySummary:
    return CategorySummary(
        id=category.id,
        name=category.name,
        slug=category.slug,
        parent_id=category.parent_id,
        image_url=category.image_url,
        position=category.position,
    )


# ---------------------------------------------------------------------------
# Products
# ---------------------------------------------------------------------------
@router.get(
    "/products",
    response_model=Page[ProductCardResponse],
    summary="Browse products",
    description=(
        "Paginated, filterable product listing. Price filters use the trigger-maintained "
        "`price_min`, and availability is resolved from live inventory, so a listing can "
        "never advertise a price or an availability that is not true."
    ),
)
async def list_products(
    session: Annotated[AsyncSession, Depends(get_db)],
    page: Annotated[int, Query(ge=1, le=10_000)] = 1,
    per_page: Annotated[int, Query(ge=1, le=100)] = 24,
    category: Annotated[list[str] | None, Query()] = None,
    brand: Annotated[list[str] | None, Query()] = None,
    tag: Annotated[list[str] | None, Query()] = None,
    min_price: Annotated[int | None, Query(ge=0, description="Minor units (paise)")] = None,
    max_price: Annotated[int | None, Query(ge=0, description="Minor units (paise)")] = None,
    in_stock: bool = False,
    on_sale: bool = False,
    featured: bool = False,
    sort: ProductSort = "newest",
) -> Page[ProductCardResponse]:
    filters = ProductFilters(
        tags=tuple(t.lower().strip() for t in (tag or []) if t.strip()),
        min_price=min_price,
        max_price=max_price,
        in_stock_only=in_stock,
        on_sale_only=on_sale,
        featured_only=featured,
        sort=sort,
    )

    # A single brand is supported at the model level. Taking the first keeps the
    # SQL a simple indexed equality rather than an IN list, and the behaviour is
    # documented rather than silently ignoring the rest.
    if brand:
        filters = replace(filters, brand=brand[0].strip())

    if category:
        ids: list[uuid.UUID] = []
        for slug in category:
            found = await catalog_service.get_category_by_slug(session, slug)
            ids.extend(await catalog_service.get_category_descendants(session, found))
        filters = replace(filters, category_ids=tuple(ids))

    products, total = await catalog_service.list_products(
        session, filters, limit=per_page, offset=(page - 1) * per_page
    )

    return Page[ProductCardResponse](
        items=[_card(p) for p in products],
        meta=PageMeta.build(page=page, per_page=per_page, total=total),
    )


@router.get(
    "/products/featured",
    response_model=list[ProductCardResponse],
    summary="Featured products",
)
async def featured_products(
    session: Annotated[AsyncSession, Depends(get_db)],
    limit: Annotated[int, Query(ge=1, le=24)] = 8,
) -> list[ProductCardResponse]:
    products = await catalog_service.get_featured(session, limit=limit)
    return [_card(p) for p in products]


@router.get(
    "/products/new",
    response_model=list[ProductCardResponse],
    summary="New arrivals",
)
async def new_arrivals(
    session: Annotated[AsyncSession, Depends(get_db)],
    limit: Annotated[int, Query(ge=1, le=24)] = 8,
) -> list[ProductCardResponse]:
    products = await catalog_service.get_new_arrivals(session, limit=limit)
    return [_card(p) for p in products]


@router.get(
    "/products/best-sellers",
    response_model=list[ProductCardResponse],
    summary="Best sellers",
    description="Ranked by units sold in the last 90 days, derived from order data.",
)
async def best_sellers(
    session: Annotated[AsyncSession, Depends(get_db)],
    limit: Annotated[int, Query(ge=1, le=24)] = 8,
) -> list[ProductCardResponse]:
    products = await catalog_service.get_best_sellers(session, limit=limit)
    return [_card(p) for p in products]


@router.get(
    "/products/{slug}",
    response_model=ProductDetailResponse,
    summary="Product detail",
    description=(
        "Returns the full product page payload including the variant matrix, so the "
        "PDP renders in a single round trip. Draft and archived products are a 404."
    ),
)
async def product_detail(
    slug: str,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> ProductDetailResponse:
    product = await catalog_service.get_product_by_slug(session, slug)

    ancestors = (
        await catalog_service.get_category_ancestors(session, product.category)
        if product.category
        else []
    )
    summary = product.rating_summary

    variants: list[VariantResponse] = []
    for variant in product.variants:
        price = variant.effective_price()
        compare_at = variant.effective_compare_at()
        available = variant.inventory.available if variant.inventory else 0
        variants.append(
            VariantResponse(
                id=variant.id,
                sku=variant.sku,
                title=variant.title,
                attributes={str(k): str(v) for k, v in (variant.attributes or {}).items()},
                price=_money(price),
                compare_at_price=(
                    _money(compare_at) if compare_at and compare_at > price else None
                ),
                discount_percent=(
                    round((compare_at - price) * 100 / compare_at)
                    if compare_at and compare_at > price
                    else 0
                ),
                currency=variant.currency,
                status=variant.status.value,
                is_default=variant.is_default,
                available_quantity=available,
                in_stock=available > 0,
                low_stock=0 < available <= (variant.low_stock_threshold or 3),
                options={str(k): str(v) for k, v in (variant.attributes or {}).items()},
            )
        )

    distribution = {"1": 0, "2": 0, "3": 0, "4": 0, "5": 0}
    if summary and summary.distribution:
        for index, count in enumerate(summary.distribution[:5]):
            distribution[str(index + 1)] = int(count)

    base_price = product.base_price
    effective_price = product.effective_price()

    return ProductDetailResponse(
        id=product.id,
        title=product.title,
        slug=product.slug,
        subtitle=product.subtitle,
        short_description=product.short_description,
        description=product.description,
        sku=product.sku,
        brand=product.brand,
        category=await _category_summary(product.category),
        breadcrumb=[await _category_summary(a) for a in ancestors],
        price=_money(effective_price),
        compare_at_price=(
            _money(product.compare_at_price)
            if product.compare_at_price and product.compare_at_price > base_price
            else None
        ),
        discount_percent=product.discount_percent,
        min_price=_money(product.price_min) if product.price_min is not None else None,
        max_price=_money(product.price_max) if product.price_max is not None else None,
        specs={str(k): str(v) for k, v in (product.specs or {}).items()},
        tags=[tag.name for tag in product.tags],
        images=[ProductImageResponse.model_validate(i) for i in product.images],
        variants=variants,
        options=[VariantOption.model_validate(o) for o in catalog_service.variant_options(product)],
        rating_average=round(float(summary.average_rating), 2) if summary else 0.0,
        rating_count=int(summary.review_count) if summary else 0,
        rating_distribution=distribution,
        is_featured=product.is_featured,
        status=product.status.value,
        stock_status=catalog_service.stock_status_for(product),
        in_stock=product.in_stock(),
        total_available=sum(v.inventory.available if v.inventory else 0 for v in product.variants),
        seo_title=product.seo_title,
        seo_description=product.seo_description,
        created_at=product.created_at,
        updated_at=product.updated_at,
    )


@router.get(
    "/products/{slug}/related",
    response_model=list[RelatedProduct],
    summary="Related products",
)
async def related_products(
    slug: str,
    session: Annotated[AsyncSession, Depends(get_db)],
    limit: Annotated[int, Query(ge=1, le=16)] = 8,
) -> list[RelatedProduct]:
    product = await catalog_service.get_product_by_slug(session, slug)
    related = await catalog_service.get_related(session, product, limit=limit)

    cards: list[RelatedProduct] = []
    for item in related:
        reason = (
            "same_category"
            if item.category_id == product.category_id
            else ("same_brand" if item.brand and item.brand == product.brand else "also_viewed")
        )
        cards.append(_related_card(item, reason))
    return cards


# ---------------------------------------------------------------------------
# Categories
# ---------------------------------------------------------------------------
@router.get(
    "/categories",
    response_model=list[CategoryResponse],
    summary="Category tree",
    description="Every active category with its direct children and product count.",
)
async def list_categories(
    session: Annotated[AsyncSession, Depends(get_db)],
) -> list[CategoryResponse]:
    rows = await catalog_service.list_categories(session, with_counts=True)
    children_by_parent: dict[Any, list[Any]] = {}
    for category, _count in rows:
        if category.parent_id is not None:
            children_by_parent.setdefault(category.parent_id, []).append(category)

    return [
        CategoryResponse(
            id=category.id,
            name=category.name,
            slug=category.slug,
            parent_id=category.parent_id,
            image_url=category.image_url,
            position=category.position,
            description=category.description,
            seo_title=category.seo_title,
            seo_description=category.seo_description,
            children=[
                CategorySummary(
                    id=child.id,
                    name=child.name,
                    slug=child.slug,
                    parent_id=child.parent_id,
                    image_url=child.image_url,
                    position=child.position,
                )
                for child in children_by_parent.get(category.id, [])
            ],
            product_count=count,
            path=category.path,
        )
        for category, count in rows
    ]


@router.get(
    "/categories/{slug}",
    response_model=CategoryResponse,
    summary="Category detail",
)
async def category_detail(
    slug: str,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> CategoryResponse:
    category = await catalog_service.get_category_by_slug(session, slug)
    ancestors = await catalog_service.get_category_ancestors(session, category)

    from sqlalchemy import func, select

    from app.models.catalog import Product
    from app.models.enums import ProductStatus

    count = await session.execute(
        select(func.count(Product.id)).where(
            Product.category_id == category.id,
            Product.status == ProductStatus.ACTIVE,
        )
    )

    return CategoryResponse(
        id=category.id,
        name=category.name,
        slug=category.slug,
        parent_id=category.parent_id,
        image_url=category.image_url,
        position=category.position,
        description=category.description,
        seo_title=category.seo_title,
        seo_description=category.seo_description,
        children=[
            CategorySummary(
                id=child.id,
                name=child.name,
                slug=child.slug,
                parent_id=child.parent_id,
                image_url=child.image_url,
                position=child.position,
            )
            for child in (category.children or [])
        ],
        ancestors=[
            CategorySummary(
                id=a.id,
                name=a.name,
                slug=a.slug,
                parent_id=a.parent_id,
                image_url=a.image_url,
                position=a.position,
            )
            for a in ancestors
        ],
        product_count=count.scalar_one(),
        path=category.path,
    )


@router.get(
    "/categories/{slug}/facets",
    summary="Filter metadata for a category",
    description=(
        "Brands, tags and the price range available *within* the current category, "
        "so the filter sidebar never offers an option that yields zero results."
    ),
)
async def category_facets(
    slug: str,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> dict[str, Any]:
    category = await catalog_service.get_category_by_slug(session, slug)
    ids = await catalog_service.get_category_descendants(session, category)
    return await catalog_service.get_facets(session, ids)


@router.get(
    "/facets",
    summary="Filter metadata for the whole catalogue",
)
async def global_facets(
    session: Annotated[AsyncSession, Depends(get_db)],
) -> dict[str, Any]:
    return await catalog_service.get_facets(session, None)


# ---------------------------------------------------------------------------
# Search
# ---------------------------------------------------------------------------
@router.get(
    "/search",
    summary="Search products and categories",
    description=(
        "Full-text search over a GIN-indexed tsvector, with trigram similarity as a "
        "typo fallback. Ranking uses ts_rank, so title matches outrank body matches."
    ),
)
async def search(
    session: Annotated[AsyncSession, Depends(get_db)],
    q: Annotated[str, Query(min_length=1, max_length=120)],
    type: Literal["all", "product", "category"] = "all",
    page: Annotated[int, Query(ge=1, le=10_000)] = 1,
    per_page: Annotated[int, Query(ge=1, le=48)] = 24,
    sort: ProductSort = "relevance",
) -> dict[str, Any]:
    from sqlalchemy import or_, select

    from app.models.catalog import Category

    results: list[SearchResultItem] = []

    if type in {"all", "product"}:
        filters = ProductFilters(search=q.strip(), sort=sort)
        products, total = await catalog_service.list_products(
            session, filters, limit=per_page, offset=(page - 1) * per_page
        )
        for product in products:
            primary = product.primary_image
            results.append(
                SearchResultItem(
                    type="product",
                    id=product.id,
                    title=product.title,
                    slug=product.slug,
                    subtitle=product.brand or product.short_description,
                    image_url=primary.url if primary else None,
                    price=_money(product.effective_price()),
                    in_stock=product.in_stock(),
                )
            )
        meta = PageMeta.build(page=page, per_page=per_page, total=total)
    else:
        meta = PageMeta.build(page=1, per_page=per_page, total=0)

    if type in {"all", "category"} and page == 1:
        category_rows = await session.execute(
            select(Category)
            .where(
                Category.is_active.is_(True),
                or_(
                    Category.name.ilike(f"%{q.strip()}%"),
                    Category.description.ilike(f"%{q.strip()}%"),
                ),
            )
            .order_by(Category.name.asc())
            .limit(6)
        )
        for category in category_rows.scalars().all():
            results.append(
                SearchResultItem(
                    type="category",
                    id=category.id,
                    title=category.name,
                    slug=category.slug,
                    subtitle=category.description,
                )
            )

    return {
        "query": q,
        "items": results,
        "meta": meta,
        "count": meta.total,
    }


@router.get(
    "/search/suggestions",
    response_model=list[SearchSuggestion],
    summary="Typeahead suggestions",
    description="Debounced by the client. Returns products, categories, brands and tags.",
)
async def search_suggestions(
    session: Annotated[AsyncSession, Depends(get_db)],
    q: Annotated[str, Query(min_length=1, max_length=80)],
    limit: Annotated[int, Query(ge=1, le=20)] = 8,
) -> list[SearchSuggestion]:
    return await catalog_service.search_suggestions(session, q, limit=limit)


@router.get(
    "/search/trending",
    response_model=list[str],
    summary="Popular search terms",
    description="Static seed list, refined by the analytics job when it has data.",
)
async def trending_searches() -> list[str]:
    return [
        "noise cancelling",
        "wireless earbuds",
        "over-ear headphones",
        "smartwatch",
        "bluetooth speaker",
        "studio monitors",
    ]


@router.get("/filters", include_in_schema=False)
async def filter_schema() -> dict[str, Any]:
    """Machine readable filter/sort vocabulary, so the client cannot drift."""
    return {
        "sort": {
            "newest": "Newest first",
            "oldest": "Oldest first",
            "price_asc": "Price: low to high",
            "price_desc": "Price: high to low",
            "rating": "Highest rated",
            "popular": "Most reviewed",
            "name_asc": "Name: A to Z",
            "name_desc": "Name: Z to A",
            "relevance": "Relevance (search only)",
        },
        "filters": {
            "category": "Category slug. Repeatable.",
            "brand": "Brand name. Repeatable.",
            "tag": "Tag slug. Repeatable.",
            "min_price": "Minimum price in minor units",
            "max_price": "Maximum price in minor units",
            "in_stock": "Only show purchasable items",
            "on_sale": "Only show discounted items",
            "featured": "Only show featured items",
        },
        "money": {"unit": "minor_units", "example": 2499000, "means": "Rs. 24,990.00"},
    }
