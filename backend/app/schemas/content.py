"""Response contracts for the content API (industries and blog).

Separate from the catalogue schemas on purpose: an industry page is editorial
content with a hand-picked product list, and forcing it through the catalogue
schemas would either lose the Markdown body or duplicate the product card shape
with slightly different fields.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class IndustrySummary(BaseModel):
    """Card-level industry data. Enough for the index grid and nothing more."""

    model_config = ConfigDict(from_attributes=True)

    id: Any
    name: str
    slug: str
    tagline: str | None = None
    summary: str | None = None
    hero_image_url: str | None = None
    #: lucide-react icon name, e.g. "factory". Null when none is set.
    icon: str | None = None
    position: int = 0
    product_count: int = 0


class IndustryDetail(IndustrySummary):
    """The full landing page.

    ``body`` is Markdown. ``product_slugs`` is a list of slugs rather than full
    product objects: the frontend already has the catalogue API for that, and
    duplicating the card shape here would guarantee the two drift apart.
    """

    body: str = ""
    product_slugs: list[str] = Field(default_factory=list)
    seo_title: str | None = None
    seo_description: str | None = None


class BlogPostSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: Any
    title: str
    slug: str
    excerpt: str
    cover_image_url: str | None = None
    cover_image_alt: str | None = None
    reading_minutes: int | None = None
    published_at: datetime | None = None
    seo_title: str | None = None
    seo_description: str | None = None


class BlogPostDetail(BlogPostSummary):
    body: str = ""
    #: Null on purpose. The live site publishes no author, so the seed leaves
    #: this empty rather than inventing a name; the UI omits the byline.
    author_name: str | None = None
    #: Compliance deadline the article is written against, e.g. a HazCom date.
    compliance_deadline: datetime | None = None
    #: ``[{"question": ..., "answer": ...}]``. Emitted as FAQPage schema.org.
    faq: list[dict[str, str]] | None = None
    related_products: list[dict[str, str]] = Field(default_factory=list)
