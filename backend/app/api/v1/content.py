"""Public content API: industries and blog.

Both are read-only here. The admin side is a later phase; what the storefront
needs right now is a way to render the industry landing pages and the knowledge
centre from seeded content rather than a hand-written array in a component.

No writes, no auth, no user-generated content. Bodies come back as Markdown
strings and are rendered by the frontend through a sanitising subset, so nothing
in this module can execute script - see ``frontend/src/components/content/
Markdown.tsx``.
"""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Path, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.core.errors import NotFoundError
from app.models.catalog import Product, ProductStatus
from app.models.content import (
    BlogCategory,
    BlogPost,
    BlogPostCategory,
    BlogPostProduct,
    Industry,
    IndustryProduct,
)
from app.schemas.common import Page, PageMeta
from app.schemas.content import (
    BlogPostDetail,
    BlogPostSummary,
    IndustryDetail,
    IndustrySummary,
)

router = APIRouter()

# --- industries -------------------------------------------------------------


@router.get("/industries", response_model=list[IndustrySummary], summary="List industries")
async def list_industries(
    session: AsyncSession = Depends(get_db),
) -> list[IndustrySummary]:
    """Active industries, in the curated display order.

    ``product_count`` is a live count of the products linked through
    ``industry_products``, not a stored column, so it cannot drift when products
    are re-categorised.
    """
    count_subquery = (
        select(func.count(IndustryProduct.product_id))
        .where(IndustryProduct.industry_id == Industry.id)
        .correlate(Industry)
        .scalar_subquery()
    )

    rows = await session.execute(
        select(Industry, count_subquery.label("product_count"))
        .where(Industry.is_active.is_(True))
        .order_by(Industry.position, Industry.name)
    )

    return [
        IndustrySummary(
            id=industry.id,
            name=industry.name,
            slug=industry.slug,
            tagline=industry.tagline,
            summary=industry.summary,
            hero_image_url=industry.hero_image_url,
            icon=industry.icon,
            position=industry.position,
            product_count=int(count or 0),
        )
        for industry, count in rows.all()
    ]


@router.get(
    "/industries/{slug}",
    response_model=IndustryDetail,
    summary="Industry landing page",
)
async def get_industry(
    slug: Annotated[str, Path(min_length=1, max_length=140)],
    session: AsyncSession = Depends(get_db),
) -> IndustryDetail:
    result = await session.execute(
        select(Industry).where(Industry.slug == slug, Industry.is_active.is_(True))
    )
    industry = result.scalar_one_or_none()
    if industry is None:
        raise NotFoundError(f"Industry '{slug}' was not found.")

    # Explicit join rather than a lazy relationship: touching `industry.products`
    # outside an awaited context raises MissingGreenlet.
    product_rows = await session.execute(
        select(Product)
        .join(IndustryProduct, IndustryProduct.product_id == Product.id)
        .where(
            IndustryProduct.industry_id == industry.id,
            Product.status == ProductStatus.ACTIVE,
        )
        .order_by(IndustryProduct.position, Product.title)
    )
    products = product_rows.scalars().all()

    return IndustryDetail(
        id=industry.id,
        name=industry.name,
        slug=industry.slug,
        tagline=industry.tagline,
        summary=industry.summary,
        body=industry.body,
        hero_image_url=industry.hero_image_url,
        icon=industry.icon,
        position=industry.position,
        product_count=len(products),
        product_slugs=[product.slug for product in products],
        seo_title=industry.seo_title,
        seo_description=industry.seo_description,
    )


# --- blog -------------------------------------------------------------------


@router.get(
    "/blog/posts",
    response_model=Page[BlogPostSummary],
    summary="List published blog posts",
)
async def list_blog_posts(
    page: Annotated[int, Query(ge=1)] = 1,
    per_page: Annotated[int, Query(ge=1, le=50)] = 12,
    category: Annotated[str | None, Query()] = None,
    session: AsyncSession = Depends(get_db),
) -> Page[BlogPostSummary]:
    """Published posts, newest first.

    The filter is on ``status = PUBLISHED`` *and* ``published_at <= now()`` so a
    post scheduled for next week does not leak early.
    """
    conditions: list[Any] = [
        BlogPost.status == "PUBLISHED",
        BlogPost.published_at.is_not(None),
        BlogPost.published_at <= func.now(),
    ]

    if category:
        conditions.append(
            select(BlogPostCategory.post_id)
            .join(BlogCategory, BlogCategory.id == BlogPostCategory.category_id)
            .where(BlogCategory.slug == category)
            .exists()
        )

    count_result = await session.execute(select(func.count(BlogPost.id)).where(*conditions))
    total = int(count_result.scalar_one())

    result = await session.execute(
        select(BlogPost)
        .where(*conditions)
        .order_by(BlogPost.published_at.desc(), BlogPost.id)
        .offset((page - 1) * per_page)
        .limit(per_page)
    )
    posts = result.scalars().all()

    return Page[BlogPostSummary](
        items=[_to_summary(post) for post in posts],
        meta=PageMeta.build(page=page, per_page=per_page, total=total),
    )


@router.get(
    "/blog/posts/{slug}",
    response_model=BlogPostDetail,
    summary="A single blog post",
)
async def get_blog_post(
    slug: Annotated[str, Path(min_length=1, max_length=220)],
    session: AsyncSession = Depends(get_db),
) -> BlogPostDetail:
    result = await session.execute(
        select(BlogPost).where(
            BlogPost.slug == slug,
            BlogPost.status == "PUBLISHED",
            BlogPost.published_at <= func.now(),
        )
    )
    post = result.scalar_one_or_none()
    if post is None:
        raise NotFoundError(f"Post '{slug}' was not found.")

    product_rows = await session.execute(
        select(Product.slug, Product.title)
        .join(BlogPostProduct, BlogPostProduct.product_id == Product.id)
        .where(BlogPostProduct.post_id == post.id, Product.status == ProductStatus.ACTIVE)
        .order_by(BlogPostProduct.position)
    )
    related = [{"slug": slug, "title": title} for slug, title in product_rows.all()]

    summary = _to_summary(post)
    return BlogPostDetail(
        **summary.model_dump(),
        body=post.body,
        author_name=post.author_name,
        compliance_deadline=post.compliance_deadline,
        faq=post.faq,
        related_products=related,
    )


def _to_summary(post: BlogPost) -> BlogPostSummary:
    return BlogPostSummary(
        id=post.id,
        title=post.title,
        slug=post.slug,
        excerpt=post.excerpt,
        cover_image_url=post.cover_image_url,
        cover_image_alt=post.cover_image_alt,
        reading_minutes=post.reading_minutes,
        published_at=post.published_at,
        seo_title=post.seo_title,
        seo_description=post.seo_description,
    )
