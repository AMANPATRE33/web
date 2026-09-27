"""Catalogue reads: listing, filtering, sorting, detail, search.

Design notes that matter for correctness and for performance:

* **One query for the page, one for the count.** The count is a separate
  ``COUNT(*)`` over the same ``WHERE`` clause. Running it as a window function
  over the result set would fetch every matching row to count them.
* **Filtering on the *live* price.** ``price_min`` is a trigger-maintained
  generated value on ``products``, so a price range filter is an indexable
  comparison rather than a join against variants on every row.
* **Stock is filtered in SQL, not in Python.** ``EXISTS`` against
  ``inventory.available > 0`` uses the partial index, so "in stock only" does
  not pull the whole catalogue into memory to be discarded.
* **Search uses the GIN-indexed tsvector** with a websearch-style prefix query,
  and falls back to trigram similarity for typos.
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any, Literal

from sqlalchemy import Select, and_, func, or_, select, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload, selectinload

from app.core.errors import NotFoundError
from app.core.logging import get_logger
from app.models.catalog import (
    Category,
    Inventory,
    Product,
    ProductTag,
    ProductVariant,
    Tag,
)
from app.models.engagement import ProductRatingSummary
from app.models.enums import ProductStatus, VariantStatus
from app.schemas.catalog import (
    SearchSuggestion,
    StockStatus,
)

logger = get_logger(__name__)

#: Case-insensitive title ordering. Sorting on ``lower(title)`` rather than
#: ``title`` makes A-Z order predictable and independent of the database
#: cluster's locale: with a locale-aware collation, "CCTV In Operation" sorts
#: before "Caution Do Not Enter", and the catalogue order would silently change
#: if the database moved to a different host.
_TITLE_SORT = func.lower(Product.title).asc()

SortKey = Literal[
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


@dataclass(slots=True)
class ProductFilters:
    """Normalised filter state for a catalogue query."""

    category_ids: tuple[uuid.UUID, ...] = ()
    brand: str | None = None
    tags: tuple[str, ...] = ()
    #: Material values, e.g. "3MM ACP". OR semantics: any of the selected.
    materials: tuple[str, ...] = ()
    #: Size labels, e.g. "18x24". OR semantics: any of the selected.
    sizes: tuple[str, ...] = ()
    min_price: int | None = None
    max_price: int | None = None
    in_stock_only: bool = False
    on_sale_only: bool = False
    featured_only: bool = False
    search: str | None = None
    sort: SortKey = "newest"

    def is_empty(self) -> bool:
        return not (
            self.category_ids
            or self.brand
            or self.tags
            or self.materials
            or self.sizes
            or self.min_price is not None
            or self.max_price is not None
            or self.in_stock_only
            or self.on_sale_only
            or self.featured_only
            or self.search
        )


def _order_by(sort: SortKey, has_search: bool) -> list[Any]:
    """Build the ORDER BY clause.

    Every ordering is fully deterministic: a tie on the sort key is broken by
    ``id``. Without the tiebreak, PostgreSQL may return equal rows in a
    different order between two requests, and a customer paging through results
    sees an item twice and misses another.
    """
    if sort == "price_asc":
        return [Product.price_min.asc().nulls_last(), Product.id.asc()]
    if sort == "price_desc":
        return [Product.price_min.desc().nulls_last(), Product.id.asc()]
    if sort == "name_asc":
        return [_TITLE_SORT, Product.id.asc()]
    if sort == "name_desc":
        return [func.lower(Product.title).desc(), Product.id.asc()]
    if sort == "oldest":
        return [Product.created_at.asc(), Product.id.asc()]
    if sort == "rating":
        # Unrated products sink rather than sorting as 5 stars.
        return [
            ProductRatingSummary.average_rating.desc().nulls_last(),
            ProductRatingSummary.review_count.desc().nulls_last(),
            Product.id.asc(),
        ]
    if sort == "popular":
        return [
            ProductRatingSummary.review_count.desc().nulls_last(),
            Product.id.asc(),
        ]
    if sort == "relevance" and has_search:
        # ts_rank is only meaningful with a search; otherwise "newest".
        return [text("rank DESC NULLS LAST"), Product.id.asc()]
    return [Product.created_at.desc(), Product.id.asc()]


def _apply_filters(stmt: Select[Any], filters: ProductFilters) -> Select[Any]:
    conditions: list[Any] = [Product.status == ProductStatus.ACTIVE]

    if filters.category_ids:
        conditions.append(Product.category_id.in_(filters.category_ids))

    if filters.brand:
        conditions.append(func.lower(Product.brand) == filters.brand.strip().lower())

    if filters.tags:
        # Products carrying *all* of the requested tags. `product_tags` is
        # indexed on tag_id, so each EXISTS is an index probe rather than a
        # sequential scan.
        for tag_slug in filters.tags:
            matching = (
                select(ProductTag.product_id)
                .join(Tag, Tag.id == ProductTag.tag_id)
                .where(Tag.slug == tag_slug, ProductTag.product_id == Product.id)
                .exists()
            )
            conditions.append(matching)

    if filters.min_price is not None:
        conditions.append(Product.price_min.is_not(None))
        conditions.append(Product.price_min >= filters.min_price)

    if filters.max_price is not None:
        conditions.append(Product.price_min.is_not(None))
        conditions.append(Product.price_min <= filters.max_price)

    if filters.on_sale_only:
        conditions.append(Product.compare_at_price.is_not(None))
        conditions.append(Product.compare_at_price > Product.price_min)

    if filters.featured_only:
        conditions.append(Product.is_featured.is_(True))

    # ------------------------------------------------------------------
    # Variant-level filters
    # ------------------------------------------------------------------
    # Material, Size and availability are all properties of a *single*
    # variant row, so they are combined into ONE EXISTS. Emitting them as
    # separate EXISTS clauses would cross-product: a product carrying
    # (3MM ACP, 12x18) and (ECO VINYL, 18x24) would wrongly match a filter
    # for material=3MM ACP *and* size=18x24, which is a combination the
    # business does not actually sell.
    variant_conditions: list[Any] = [
        ProductVariant.product_id == Product.id,
        ProductVariant.status == VariantStatus.ACTIVE,
    ]

    if filters.materials:
        variant_conditions.append(
            ProductVariant.attributes["Material"].astext.in_(list(filters.materials))
        )
    if filters.sizes:
        variant_conditions.append(ProductVariant.attributes["Size"].astext.in_(list(filters.sizes)))

    needs_inventory = filters.in_stock_only
    if filters.materials or filters.sizes or needs_inventory:
        variant_query = select(ProductVariant.id)
        if needs_inventory:
            # `available` is a generated column, so this is an indexable
            # predicate rather than arithmetic in the WHERE clause.
            variant_query = variant_query.join(
                Inventory, Inventory.variant_id == ProductVariant.id
            ).where(Inventory.available > 0)
        conditions.append(variant_query.where(*variant_conditions).exists())

    return stmt.where(and_(*conditions))


def _apply_search(stmt: Select[Any], search: str) -> Select[Any]:
    """Full-text search with prefix matching, plus a trigram fallback.

    ``websearch_to_tsquery`` gives users quoted phrases, ``-exclusion`` and
    ``OR`` for free, and - importantly - never raises on malformed input the way
    ``to_tsquery`` does.
    """
    sanitised = search.strip()
    if not sanitised:
        return stmt

    vector_match = Product.search_vector.op("@@")(func.websearch_to_tsquery("english", sanitised))
    # Trigram similarity catches typos a stemmed index cannot: "corrisive" has
    # no matching lexeme, but shares most of its trigrams with "corrosive".
    # Matched against the title *and* the description, because a product's
    # distinguishing words usually live in the body copy rather than the title.
    trigram_match = or_(
        func.similarity(Product.title, sanitised) > 0.3,
        func.similarity(Product.description, sanitised) > 0.3,
    )

    return stmt.where(or_(vector_match, trigram_match))


async def list_products(
    session: AsyncSession,
    filters: ProductFilters,
    *,
    limit: int,
    offset: int,
) -> tuple[Sequence[Product], int]:
    """Return one page of products and the total match count."""
    base = _apply_filters(select(Product), filters)

    if filters.search:
        base = _apply_search(base, filters.search)
        # ts_rank is only valid when the query references the vector.
        base = base.add_columns(
            func.ts_rank(
                Product.search_vector,
                func.websearch_to_tsquery("english", filters.search.strip()),
            ).label("rank")
        )

    count_stmt = _apply_filters(
        _apply_search(select(func.count(Product.id)), filters.search)
        if filters.search
        else select(func.count(Product.id)),
        filters,
    )
    total = (await session.execute(count_stmt)).scalar_one()

    order = _order_by(filters.sort, bool(filters.search))
    if filters.sort == "relevance" and not filters.search:
        order = _order_by("newest", False)

    stmt = (
        base.options(
            selectinload(Product.images),
            selectinload(Product.variants).selectinload(ProductVariant.inventory),
            selectinload(Product.category),
            selectinload(Product.tags),
            joinedload(Product.rating_summary),
        )
        .order_by(*order)
        .limit(limit)
        .offset(offset)
    )

    result = await session.execute(stmt)
    rows = result.all()
    products = [row[0] for row in rows]
    return products, int(total)


async def get_product_by_slug(
    session: AsyncSession, slug: str, *, include_unpublished: bool = False
) -> Product:
    """Load one product with everything the detail page needs.

    ``include_unpublished`` exists for the admin preview route. The public route
    never sets it, so a draft or archived product is a 404 to a shopper rather
    than a page that renders and then fails to price.
    """
    conditions = [Product.slug == slug.strip().lower()]
    if not include_unpublished:
        conditions.append(Product.status == ProductStatus.ACTIVE)

    stmt = (
        select(Product)
        .where(and_(*conditions))
        .options(
            selectinload(Product.images),
            selectinload(Product.variants).selectinload(ProductVariant.inventory),
            selectinload(Product.category),
            selectinload(Product.tags),
            joinedload(Product.rating_summary),
        )
        .limit(1)
    )
    result = await session.execute(stmt)
    product = result.scalar_one_or_none()

    if product is None:
        raise NotFoundError("We could not find that product.", code="product_not_found")
    return product


async def get_products_by_slugs(session: AsyncSession, slugs: Sequence[str]) -> list[Product]:
    if not slugs:
        return []
    stmt = (
        select(Product)
        .where(Product.slug.in_([s.strip().lower() for s in slugs]))
        .options(
            selectinload(Product.images),
            selectinload(Product.variants).selectinload(ProductVariant.inventory),
            selectinload(Product.category),
            selectinload(Product.tags),
            joinedload(Product.rating_summary),
        )
    )
    result = await session.execute(stmt)
    by_slug = {p.slug: p for p in result.scalars().all()}
    # Preserve the caller's ordering, which usually encodes relevance.
    return [by_slug[s.strip().lower()] for s in slugs if s.strip().lower() in by_slug]


async def get_featured(
    session: AsyncSession, *, limit: int = 8, category_id: uuid.UUID | None = None
) -> list[Product]:
    stmt = (
        select(Product)
        .where(
            Product.status == ProductStatus.ACTIVE,
            Product.is_featured.is_(True),
        )
        .options(
            selectinload(Product.images),
            selectinload(Product.variants).selectinload(ProductVariant.inventory),
            selectinload(Product.category),
            selectinload(Product.tags),
            joinedload(Product.rating_summary),
        )
        .order_by(Product.created_at.desc(), Product.id.asc())
        .limit(limit)
    )
    if category_id is not None:
        stmt = stmt.where(Product.category_id == category_id)
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def get_new_arrivals(
    session: AsyncSession, *, limit: int = 8, category_id: uuid.UUID | None = None
) -> list[Product]:
    stmt = (
        select(Product)
        .where(Product.status == ProductStatus.ACTIVE)
        .options(
            selectinload(Product.images),
            selectinload(Product.variants).selectinload(ProductVariant.inventory),
            selectinload(Product.category),
            selectinload(Product.tags),
            joinedload(Product.rating_summary),
        )
        .order_by(Product.created_at.desc(), Product.id.asc())
        .limit(limit)
    )
    if category_id is not None:
        stmt = stmt.where(Product.category_id == category_id)
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def get_best_sellers(
    session: AsyncSession, *, limit: int = 8, category_id: uuid.UUID | None = None
) -> list[Product]:
    """Ranked by units sold in the last 90 days.

    Derived from ``order_items`` rather than a stored counter, so it cannot
    drift from the orders that actually happened. Bounded by a date filter so
    the aggregation stays cheap on a large table.
    """
    from datetime import UTC, datetime, timedelta

    from app.models.enums import OrderStatus
    from app.models.orders import Order, OrderItem

    since = datetime.now(UTC) - timedelta(days=90)
    units = (
        select(OrderItem.product_id, func.sum(OrderItem.quantity).label("units"))
        .join(Order, Order.id == OrderItem.order_id)
        .where(
            Order.paid_at.is_not(None),
            Order.paid_at >= since,
            Order.status.notin_([OrderStatus.CANCELLED, OrderStatus.REFUNDED]),
        )
        .group_by(OrderItem.product_id)
        .subquery()
    )

    stmt = (
        select(Product)
        .join(units, units.c.product_id == Product.id)
        .where(Product.status == ProductStatus.ACTIVE)
        .options(
            selectinload(Product.images),
            selectinload(Product.variants).selectinload(ProductVariant.inventory),
            selectinload(Product.category),
            selectinload(Product.tags),
            joinedload(Product.rating_summary),
        )
        .order_by(units.c.units.desc(), Product.id.asc())
        .limit(limit)
    )
    if category_id is not None:
        stmt = stmt.where(Product.category_id == category_id)

    result = await session.execute(stmt)
    return list(result.scalars().all())


async def get_related(session: AsyncSession, product: Product, *, limit: int = 8) -> list[Product]:
    """Related products: same category first, then same brand.

    Excludes the product itself and anything unbuyable, because recommending an
    out-of-stock item is worse than recommending nothing.
    """
    stmt = (
        select(Product)
        .where(
            Product.status == ProductStatus.ACTIVE,
            Product.id != product.id,
        )
        .options(
            selectinload(Product.images),
            selectinload(Product.variants).selectinload(ProductVariant.inventory),
            selectinload(Product.category),
            selectinload(Product.tags),
            joinedload(Product.rating_summary),
        )
        .order_by(
            # Same category first, then same brand, then newest.
            (Product.category_id == product.category_id).desc(),
            (Product.brand == product.brand).desc() if product.brand else False,
            Product.created_at.desc(),
            Product.id.asc(),
        )
        .limit(limit)
    )
    result = await session.execute(stmt)
    related = list(result.scalars().all())

    if len(related) < limit and product.brand:
        seen = {p.id for p in related} | {product.id}
        filler_stmt = (
            select(Product)
            .where(
                Product.status == ProductStatus.ACTIVE,
                Product.brand == product.brand,
                Product.id.notin_(seen),
            )
            .options(
                selectinload(Product.images),
                selectinload(Product.variants).selectinload(ProductVariant.inventory),
                selectinload(Product.category),
                selectinload(Product.tags),
                joinedload(Product.rating_summary),
            )
            .order_by(Product.created_at.desc(), Product.id.asc())
            .limit(limit - len(related))
        )
        filler = await session.execute(filler_stmt)
        related.extend(filler.scalars().all())

    return related


# ---------------------------------------------------------------------------
# Categories
# ---------------------------------------------------------------------------
async def list_categories(
    session: AsyncSession, *, only_active: bool = True, with_counts: bool = True
) -> list[tuple[Category, int]]:
    """All categories, each paired with its count of active products.

    The count is a correlated scalar subquery, so a single query returns the
    tree with counts - no per-category round trip.
    """
    count_expr = (
        select(func.count(Product.id))
        .where(
            Product.category_id == Category.id,
            Product.status == ProductStatus.ACTIVE,
        )
        .correlate(Category)
        .scalar_subquery()
    )

    stmt = select(Category)
    if with_counts:
        stmt = stmt.add_columns(count_expr.label("product_count"))
    if only_active:
        stmt = stmt.where(Category.is_active.is_(True))

    stmt = stmt.order_by(Category.position.asc(), func.lower(Category.name).asc())
    result = await session.execute(stmt)

    if with_counts:
        return [(row[0], int(row[1])) for row in result.all()]
    return [(row, 0) for row in result.scalars().all()]


async def get_category_by_slug(
    session: AsyncSession, slug: str, *, include_inactive: bool = False
) -> Category:
    conditions = [Category.slug == slug.strip().lower()]
    if not include_inactive:
        conditions.append(Category.is_active.is_(True))

    result = await session.execute(
        select(Category).where(and_(*conditions)).options(selectinload(Category.children)).limit(1)
    )
    category = result.scalar_one_or_none()
    if category is None:
        raise NotFoundError("We could not find that category.", code="category_not_found")
    return category


async def get_category_ancestors(session: AsyncSession, category: Category) -> list[Category]:
    """Root-to-parent chain, resolved from the materialised ``path`` column.

    One indexed query instead of a recursive CTE per breadcrumb render.
    """
    ids = category.ancestor_ids()
    if not ids:
        return []
    result = await session.execute(
        select(Category).where(Category.id.in_(ids)).order_by(Category.position.asc())
    )
    found = {c.id: c for c in result.scalars().all()}
    return [found[i] for i in ids if i in found]


async def get_category_descendants(session: AsyncSession, category: Category) -> list[uuid.UUID]:
    """Self plus every descendant id.

    A child of ``category`` stores ``path = <category.path>,<category.id>``,
    because ``path`` holds the *ancestors* of a row excluding itself. So the
    descendant prefix is that value with no trailing separator - a trailing
    ``,`` would miss every direct child, which is the bug this shape invites.
    """
    base = f"{category.path},{category.id}" if category.path else str(category.id)
    result = await session.execute(
        select(Category.id).where(or_(Category.id == category.id, Category.path.like(f"{base}%")))
    )
    return [row[0] for row in result.all()]


async def get_facets(
    session: AsyncSession, category_ids: Sequence[uuid.UUID] | None = None
) -> dict[str, Any]:
    """Filter metadata for the listing sidebar.

    Computed over the *current* category scope so the sidebar never offers a
    brand or a price band that yields zero results.
    """
    scope = [Product.status == ProductStatus.ACTIVE]
    if category_ids:
        scope.append(Product.category_id.in_(list(category_ids)))

    brand_rows = await session.execute(
        select(Product.brand, func.count(Product.id))
        .where(*scope, Product.brand.is_not(None))
        .group_by(Product.brand)
        .order_by(func.count(Product.id).desc())
    )
    brands = [{"value": row[0], "count": int(row[1])} for row in brand_rows.all()]

    price_row = await session.execute(
        select(func.min(Product.price_min), func.max(Product.price_min)).where(*scope)
    )
    min_price, max_price = price_row.one()

    tag_rows = await session.execute(
        select(Tag.slug, Tag.name, func.count())
        .select_from(Tag)
        .join(ProductTag, ProductTag.tag_id == Tag.id)
        .join(Product, Product.id == ProductTag.product_id)
        .where(*scope)
        .group_by(Tag.slug, Tag.name)
        .order_by(func.count().desc())
        .limit(24)
    )
    tags = [{"slug": row[0], "name": row[1], "count": int(row[2])} for row in tag_rows.all()]

    # Material and Size facets. These are variant attributes, so they are
    # aggregated from product_variants joined to the in-scope products. The
    # counts are the number of *products* available in that option, which is
    # what a shopper filtering a grid actually wants to know.
    variant_scope = [Product.status == ProductStatus.ACTIVE]
    if category_ids:
        variant_scope.append(Product.category_id.in_(list(category_ids)))

    material_rows = await session.execute(
        select(
            ProductVariant.attributes["Material"].astext.label("value"),
            func.count(func.distinct(ProductVariant.product_id)),
        )
        .join(Product, Product.id == ProductVariant.product_id)
        .where(*variant_scope, ProductVariant.status == VariantStatus.ACTIVE)
        .group_by("value")
        .order_by("value")
    )
    materials = [{"value": row[0], "count": int(row[1])} for row in material_rows.all() if row[0]]

    size_rows = await session.execute(
        select(
            ProductVariant.attributes["Size"].astext.label("value"),
            func.count(func.distinct(ProductVariant.product_id)),
        )
        .join(Product, Product.id == ProductVariant.product_id)
        .where(*variant_scope, ProductVariant.status == VariantStatus.ACTIVE)
        .group_by("value")
        .order_by("value")
    )
    sizes = [{"value": row[0], "count": int(row[1])} for row in size_rows.all() if row[0]]

    return {
        "brands": brands,
        "tags": tags,
        "materials": materials,
        "sizes": sizes,
        "price_range": {
            "min": int(min_price) if min_price is not None else 0,
            "max": int(max_price) if max_price is not None else 0,
        },
    }


# ---------------------------------------------------------------------------
# Search
# ---------------------------------------------------------------------------
async def search_suggestions(
    session: AsyncSession, term: str, *, limit: int = 8
) -> list[SearchSuggestion]:
    """Typeahead suggestions across products, categories, brands and tags.

    Each source is queried independently and merged, so a term matching a
    category and a product surfaces both. Results are de-duplicated by text.
    """
    needle = term.strip()
    if len(needle) < 2:
        return []

    prefix = f"{needle.lower()}%"

    product_rows = await session.execute(
        select(Product.id, Product.title, Product.slug)
        .where(
            Product.status == ProductStatus.ACTIVE,
            or_(
                Product.title.ilike(f"%{needle}%"),
                Product.search_vector.op("@@")(func.plainto_tsquery("english", needle)),
            ),
        )
        .order_by(
            # Prefix matches first, then shortest title: "Aure" over
            # "Aurelius One Studio Monitor Reference".
            (func.lower(Product.title).like(prefix)).desc(),
            func.length(Product.title).asc(),
        )
        .limit(limit)
    )

    category_rows = await session.execute(
        select(Category.id, Category.name, Category.slug)
        .where(Category.is_active.is_(True), Category.name.ilike(f"%{needle}%"))
        .order_by(func.length(Category.name).asc())
        .limit(3)
    )

    brand_rows = await session.execute(
        select(Product.brand, func.count(Product.id))
        .where(
            Product.status == ProductStatus.ACTIVE,
            Product.brand.ilike(f"{prefix}"),
        )
        .group_by(Product.brand)
        .order_by(func.count(Product.id).desc())
        .limit(3)
    )

    tag_rows = await session.execute(
        select(Tag.slug, Tag.name, func.count())
        .select_from(Tag)
        .join(ProductTag, ProductTag.tag_id == Tag.id)
        .where(Tag.name.ilike(f"{prefix}"))
        .group_by(Tag.slug, Tag.name)
        .order_by(func.count().desc())
        .limit(3)
    )

    suggestions: list[SearchSuggestion] = []
    seen: set[str] = set()

    for row in product_rows.all():
        key = row[1].lower()
        if key in seen:
            continue
        seen.add(key)
        suggestions.append(
            SearchSuggestion(text=row[1], type="product", slug=row[2], product_id=row[0])
        )

    for row in category_rows.all():
        key = row[1].lower()
        if key in seen:
            continue
        seen.add(key)
        suggestions.append(SearchSuggestion(text=row[1], type="category", slug=row[2]))

    for row in brand_rows.all():
        key = str(row[0]).lower()
        if key in seen:
            continue
        seen.add(key)
        suggestions.append(SearchSuggestion(text=row[0], type="brand"))

    for row in tag_rows.all():
        key = row[1].lower()
        if key in seen:
            continue
        seen.add(key)
        suggestions.append(SearchSuggestion(text=row[1], type="tag", slug=row[0]))

    return suggestions[:limit]


# ---------------------------------------------------------------------------
# Presentation helpers
# ---------------------------------------------------------------------------
def stock_status_for(product: Product, *, low_stock_threshold: int = 3) -> StockStatus:
    """Classify availability for display.

    Derived from the live variant inventory, never from a stored flag, so a
    product cannot be advertised as available after its last unit sells.
    """
    purchasable = [v for v in product.variants if v.status == VariantStatus.ACTIVE]
    if not purchasable:
        return "out_of_stock"

    total = sum(v.inventory.available if v.inventory else 0 for v in purchasable)
    if total <= 0:
        return "out_of_stock"
    if total <= low_stock_threshold:
        return "low_stock"
    return "in_stock"


def available_colors(product: Product) -> list[str]:
    """Distinct colour values across purchasable variants, for card swatches."""
    colors: list[str] = []
    for variant in product.variants:
        if variant.status == VariantStatus.ACTIVE:
            colour = variant.option("Colour") or variant.option("Color")
            if colour and colour not in colors:
                colors.append(colour)
    return colors


def variant_options(product: Product) -> list[Any]:
    """Build the variant matrix axes for the PDP selector.

    Groups every active variant's attributes into axes and records, for each
    value, which variant ids carry it. The UI uses that map to disable a
    colour/size combination that does not exist or is sold out, instead of
    letting a shopper select a combination and fail at checkout.
    """
    from app.schemas.catalog import VariantOption

    axes: dict[str, dict[str, list[uuid.UUID]]] = {}
    for variant in product.variants:
        if variant.status != VariantStatus.ACTIVE:
            continue
        for key, value in variant.attributes.items():
            label = str(value)
            axes.setdefault(str(key), {}).setdefault(label, []).append(variant.id)

    ordered: list[VariantOption] = []
    # Stable axis order: the first variant's attribute order, then any others.
    axis_names: list[str] = []
    for variant in product.variants:
        if variant.status != VariantStatus.ACTIVE:
            continue
        for key in variant.attributes:
            if str(key) not in axis_names:
                axis_names.append(str(key))
    for name in axis_names:
        values = axes.get(name, {})
        ordered.append(
            VariantOption(
                name=name,
                values=sorted(values.keys()),
                variant_ids_by_value=values,
            )
        )
    return ordered
