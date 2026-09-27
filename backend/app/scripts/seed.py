"""Idempotent seed script for Safety Poster Prints.

Run with::

    python -m app.scripts.seed                     # catalogue + content
    python -m app.scripts.seed --reset             # wipe catalogue, rebuild
    python -m app.scripts.seed --admin-email a@b.com

Idempotent: upserts on natural keys (slug, sku, code, email) so a second run
leaves the same rows and the same ids. That matters for debugging - a seed that
duplicates on every run makes a bug report impossible to reproduce.

Pricing model
-------------
A product carries one ``base_price``: the price of the smallest offered size in
eco vinyl. Every other variant price is derived::

    price = base_price * (size_area / 96) * material_ratio

rounded to the nearest rupee. This reproduces the live catalogue's observed
spread - Electrical Safety runs Rs.80 at the base and Rs.8,800 at the top of
the size and material matrix - to within a few rupees, and it means the business
maintains **one** number per product rather than a full price matrix.

Reviews and ratings are deliberately not seeded. The live site publishes no
verifiable reviews, and fabricating them is not an acceptable placeholder.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path

from app.core.config import get_settings
from app.core.logging import configure_logging, get_logger
from app.db.session import get_engine, session_scope
from app.models.catalog import (
    Category,
    Inventory,
    InventoryMovement,
    Product,
    ProductImage,
    ProductTag,
    ProductVariant,
    Tag,
)
from app.models.commerce import Coupon, ShippingMethod
from app.models.content import Industry, IndustryProduct
from app.models.enums import (
    InventoryReason,
    ProductStatus,
    ShippingMethodCode,
    UserRole,
    VariantStatus,
)
from app.models.identity import Profile
from app.models.ops import IdempotentCounter
from app.scripts import seed_data as data
from app.scripts.placeholders import generate_category_image, generate_product_images
from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

logger = get_logger(__name__)

#: backend/app/scripts/seed.py -> parents: [scripts, app, backend, repo root]
REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_IMAGE_DIR = REPO_ROOT / "frontend" / "public" / "seed"

#: Business details verified from the public site. See
#: docs/REFERENCE_SITE_ANALYSIS.md. Deliberately the only business facts
#: published by the application, because they are the only ones verified.
BUSINESS = {
    "name": "Safety Poster Prints",
    "tagline": "India's #1 Safety Posters Store",
    "description": (
        "High-quality safety posters for industries, offices and workplaces - "
        "durable, laminated and ready to install."
    ),
    "email": "safetyposterprint@gmail.com",
    "phone": "+91 83200 50573",
    "address": (
        "GF-40, 41, 42, Real Square, Ankleshwar - Valia Rd, opp. Sanatan School, "
        "GIDC, Ankleshwar, Kosamdi, Gujarat 393002"
    ),
    "instagram": "https://www.instagram.com/safetypostersprint",
}


def variant_price(base_price: int, size_area: int, material_ratio: float) -> int:
    """Derive a variant price from the product base price.

    Integer arithmetic only, rounded to the nearest rupee. Floats are avoided
    here because a price that varies by a paisa depending on rounding mode is
    a reconciliation problem at month end.
    """
    size_ratio = size_area / data.BASE_AREA
    exact = base_price * size_ratio * material_ratio
    # Round to the nearest rupee: (x + 50) // 100 for minor units.
    return int((exact + 50) // 100) * 100


class Seeder:
    def __init__(self, session: AsyncSession, image_dir: Path) -> None:
        self.session = session
        self.image_dir = image_dir
        self.stats: dict[str, int] = {}
        self.category_ids: dict[str, uuid.UUID] = {}
        self.tag_ids: dict[str, uuid.UUID] = {}
        self.material_by_code = {m.code: m for m in data.MATERIALS}
        self.size_by_label = {s.label: s for s in data.SIZES}

    def _count(self, key: str, amount: int = 1) -> None:
        self.stats[key] = self.stats.get(key, 0) + amount

    # ------------------------------------------------------------------
    # Taxonomy
    # ------------------------------------------------------------------
    async def seed_categories(self) -> None:
        self.image_dir.mkdir(parents=True, exist_ok=True)
        for spec in data.CATEGORIES:
            image_url = generate_category_image(
                slug=spec.slug,
                name=spec.name,
                out_dir=self.image_dir,
                signal=spec.signal,
            )
            existing = await self.session.execute(
                select(Category).where(Category.slug == spec.slug)
            )
            row = existing.scalar_one_or_none()
            if row is None:
                row = Category(id=uuid.uuid4(), slug=spec.slug)
                self.session.add(row)

            row.name = spec.name
            row.description = spec.description
            row.parent_id = None
            row.position = spec.position
            row.image_url = image_url
            row.is_active = True
            row.seo_title = spec.seo_title
            row.seo_description = spec.seo_description
            await self.session.flush()

            self.category_ids[spec.slug] = row.id
            self._count("categories")

    async def seed_tags(self) -> None:
        """Tags are derived from the tag vocabulary actually used by products."""
        used: set[tuple[str, str]] = set()
        for product in data.PRODUCTS:
            for slug in product.tags:
                used.add((_title_from_slug(slug), slug))

        for name, slug in sorted(used):
            existing = await self.session.execute(select(Tag).where(Tag.slug == slug))
            row = existing.scalar_one_or_none()
            if row is None:
                row = Tag(id=uuid.uuid4(), name=name, slug=slug)
                self.session.add(row)
                await self.session.flush()
            self.tag_ids[slug] = row.id
        self._count("tags", len(self.tag_ids))

    # ------------------------------------------------------------------
    # Catalogue
    # ------------------------------------------------------------------
    async def seed_products(self) -> None:
        for spec in data.PRODUCTS:
            category_id = self.category_ids.get(spec.category_slug)
            if category_id is None:
                raise RuntimeError(
                    f"product {spec.slug!r} references unknown category {spec.category_slug!r}"
                )

            category_spec = next(c for c in data.CATEGORIES if c.slug == spec.category_slug)
            sizes = spec.size_labels or data.SIZE_PROFILES[category_spec.size_profile]
            materials = spec.material_codes or [m.code for m in data.MATERIALS]

            # The primary image carries the first size/material combination, so
            # the caption printed on the placeholder matches the default choice.
            images = generate_product_images(
                sku=spec.sku,
                title=spec.title,
                brand=BUSINESS["name"],
                shape="triangle",
                category_slug=spec.category_slug,
                variant_count=3,
                out_dir=self.image_dir,
                signal=category_spec.signal,
                size_label=sizes[0],
                material=materials[0],
            )

            existing = await self.session.execute(select(Product).where(Product.slug == spec.slug))
            row = existing.scalar_one_or_none()
            if row is None:
                row = Product(
                    id=uuid.uuid4(),
                    slug=spec.slug,
                    published_at=datetime.now(UTC),
                )
                self.session.add(row)

            row.title = spec.title
            row.short_description = spec.short_description
            row.description = spec.description
            row.subtitle = None
            row.sku = spec.sku
            row.brand = BUSINESS["name"]
            row.category_id = category_id
            row.base_price = spec.base_price
            # The product-level compare-at is scaled by the same factor that
            # produced `price_min`, so the card's "from Rs.X was Rs.Y" pair
            # refers to the same (smallest, cheapest) variant. Storing the
            # unscaled base would make the reference price lower than the
            # minimum selling price and the discount would never display.
            min_size = self.size_by_label[sizes[0]]
            row.compare_at_price = (
                variant_price(spec.compare_at_price, min_size.area_sq_in, 1.0)
                if spec.compare_at_price
                else None
            )
            row.status = ProductStatus.ACTIVE
            row.is_featured = spec.featured
            row.specs = spec.specs
            row.seo_title = f"{spec.title} | {BUSINESS['name']}"
            row.seo_description = spec.short_description
            row.seo_keywords = list(spec.tags)
            await self.session.flush()

            await self._sync_images(row, images)
            await self._sync_variants(row, spec, sizes, materials)
            await self._sync_tags(row, spec)
            self._count("products")

    async def _sync_images(self, product: Product, images: list) -> None:
        existing = await self.session.execute(
            select(ProductImage).where(ProductImage.product_id == product.id)
        )
        have = {img.url: img for img in existing.scalars().all()}

        for position, generated in enumerate(images):
            if generated.path in have:
                image = have[generated.path]
                image.alt_text = generated.alt_text
                image.position = position
                image.is_primary = position == 0
                continue
            self.session.add(
                ProductImage(
                    id=uuid.uuid4(),
                    product_id=product.id,
                    url=generated.path,
                    alt_text=generated.alt_text,
                    position=position,
                    is_primary=position == 0,
                    width=generated.width,
                    height=generated.height,
                )
            )
            self._count("images")

    async def _sync_variants(
        self,
        product: Product,
        spec: data.SeedProduct,
        sizes: list[str],
        materials: list[str],
    ) -> None:
        """Create the material x size matrix, one inventory row per variant."""
        existing = await self.session.execute(
            select(ProductVariant).where(ProductVariant.product_id == product.id)
        )
        by_sku = {v.sku: v for v in existing.scalars().all()}

        position = 0
        for size_label in sizes:
            size_spec = self.size_by_label[size_label]
            for material_code in materials:
                material = self.material_by_code[material_code]
                sku = f"{spec.sku}-{_sku_token(material_code)}-{_sku_token(size_label)}"
                price = variant_price(spec.base_price, size_spec.area_sq_in, material.ratio)
                # The compare-at price scales with the same size/material factors.
                # Reusing the base figure would put a large ACP variant's
                # reference price *below* its own price, and the board would
                # never register as discounted at all.
                compare_at = (
                    variant_price(spec.compare_at_price, size_spec.area_sq_in, material.ratio)
                    if spec.compare_at_price
                    else None
                )

                variant = by_sku.get(sku)
                if variant is None:
                    variant = ProductVariant(id=uuid.uuid4(), sku=sku)
                    self.session.add(variant)
                    self._count("variants")

                # Both axes are always written, even when the price comes from
                # the product, so the variant matrix on the PDP is complete and
                # filtering by material or size is uniform across the catalogue.
                variant.product_id = product.id
                variant.title = f"{size_label} - {material_code}"
                variant.attributes = {"Material": material_code, "Size": size_label}
                variant.price_override = price
                variant.compare_at_price = compare_at
                variant.status = VariantStatus.ACTIVE
                variant.position = position
                variant.is_default = position == 0
                variant.low_stock_threshold = 4
                await self.session.flush()

                await self._sync_inventory(variant, spec, material_code, size_label)
                position += 1

    @staticmethod
    def _is_sold_out(sku: str, material_code: str, size_label: str) -> bool:
        """Deterministically mark roughly one variant in twelve as sold out.

        Uses a stable hash so re-running the seed reproduces the same gaps. It
        is checked against the digit sum rather than the last character, because
        the last character is dictated by the size label and would only ever
        select one or two sizes. Every product still has at least one
        purchasable option, so none becomes entirely unbuyable.
        """
        token = _sku_token(f"{sku}{material_code}{size_label}")
        return sum(int(ch) for ch in token if ch.isdigit()) % 12 == 0

    async def _sync_inventory(
        self,
        variant: ProductVariant,
        spec: data.SeedProduct,
        material_code: str,
        size_label: str,
    ) -> None:
        stock = spec.stock_by_material.get(material_code, int(60 * spec.stock_ratio))
        # A deterministic slice of variants is sold out so the sold-out UI states
        # are exercised during development rather than discovered in production.
        # Keyed on the SKU rather than the material so the whole catalogue is not
        # uniformly out of stock on one axis.
        if self._is_sold_out(spec.sku, material_code, size_label):
            stock = 0

        result = await self.session.execute(
            select(Inventory).where(Inventory.variant_id == variant.id)
        )
        inv = result.scalar_one_or_none()

        if inv is None:
            self.session.add(
                Inventory(
                    id=uuid.uuid4(),
                    variant_id=variant.id,
                    quantity=stock,
                    reserved=0,
                    low_stock_threshold=4,
                    reorder_point=8,
                )
            )
            self.session.add(
                InventoryMovement(
                    id=uuid.uuid4(),
                    variant_id=variant.id,
                    delta=stock,
                    quantity_after=stock,
                    reserved_delta=0,
                    reason=InventoryReason.RESTOCK,
                    note="initial seed stock",
                )
            )
            self._count("inventory")
        else:
            inv.quantity = stock
            if inv.reserved > stock:
                inv.reserved = stock

    async def _sync_tags(self, product: Product, spec: data.SeedProduct) -> None:
        result = await self.session.execute(
            select(ProductTag).where(ProductTag.product_id == product.id)
        )
        have = {row.tag_id for row in result.scalars().all()}

        for slug in spec.tags:
            tag_id = self.tag_ids.get(slug)
            if tag_id is None or tag_id in have:
                continue
            self.session.add(ProductTag(product_id=product.id, tag_id=tag_id))
            have.add(tag_id)
            self._count("product_tags")

    # ------------------------------------------------------------------
    # Industries
    # ------------------------------------------------------------------
    async def seed_industries(self) -> None:
        for spec in data.INDUSTRIES:
            existing = await self.session.execute(
                select(Industry).where(Industry.slug == spec.slug)
            )
            row = existing.scalar_one_or_none()
            if row is None:
                row = Industry(id=uuid.uuid4(), slug=spec.slug)
                self.session.add(row)

            row.name = spec.name
            row.tagline = spec.tagline
            row.summary = spec.summary
            row.body = spec.body
            row.icon = spec.icon
            row.position = spec.position
            row.is_active = True
            row.seo_title = spec.seo_title
            row.seo_description = spec.seo_description
            await self.session.flush()

            # Curated product picks, in the order the copy references them.
            for position, product_slug in enumerate(spec.product_slugs):
                product_result = await self.session.execute(
                    select(Product).where(Product.slug == product_slug)
                )
                product = product_result.scalar_one_or_none()
                if product is None:
                    logger.warning(
                        "industry_product_missing", slug=product_slug, industry=spec.slug
                    )
                    continue
                self.session.add(
                    IndustryProduct(
                        industry_id=row.id,
                        product_id=product.id,
                        position=position,
                    )
                )
            self._count("industries")

    # ------------------------------------------------------------------
    # Commerce configuration
    # ------------------------------------------------------------------
    async def seed_shipping(self) -> None:
        for spec in data.SHIPPING_METHODS:
            code = ShippingMethodCode(str(spec["code"]))
            existing = await self.session.execute(
                select(ShippingMethod).where(ShippingMethod.code == code)
            )
            row = existing.scalar_one_or_none()
            if row is None:
                row = ShippingMethod(id=uuid.uuid4(), code=code)
                self.session.add(row)
            row.name = str(spec["name"])
            row.description = str(spec["description"])
            row.price = int(spec["price"])  # type: ignore[arg-type]
            row.free_above = spec["free_above"]  # type: ignore[assignment]
            row.estimated_days_min = int(spec["estimated_days_min"])  # type: ignore[arg-type]
            row.estimated_days_max = int(spec["estimated_days_max"])  # type: ignore[arg-type]
            row.position = int(spec["position"])  # type: ignore[arg-type]
            row.is_active = True
            self._count("shipping_methods")
        await self.session.flush()

    async def seed_coupons(self) -> None:
        now = datetime.now(UTC)
        for spec in data.COUPONS:
            existing = await self.session.execute(select(Coupon).where(Coupon.code == spec.code))
            row = existing.scalar_one_or_none()
            if row is None:
                row = Coupon(id=uuid.uuid4(), code=spec.code)
                self.session.add(row)
            row.description = spec.description
            row.coupon_type = spec.coupon_type  # type: ignore[assignment]
            row.value = spec.value
            row.max_discount_amount = spec.max_discount_amount
            row.min_order_amount = spec.min_order_amount
            row.starts_at = now - timedelta(days=1)
            row.expires_at = (
                now + timedelta(days=spec.expires_in_days)
                if spec.expires_in_days is not None
                else None
            )
            row.usage_limit = spec.usage_limit
            row.per_user_limit = spec.per_user_limit
            row.is_active = spec.is_active
            self._count("coupons")
        await self.session.flush()

    async def seed_admin(self, email: str, full_name: str = "Store Admin") -> None:
        """Grant ADMIN to an existing account.

        The Supabase auth user must already exist; creating credentials from a
        seed script would invent a password the operator never chose. Documented
        in the README instead.
        """
        normalised = email.strip().lower()
        existing = await self.session.execute(select(Profile).where(Profile.email == normalised))
        row = existing.scalar_one_or_none()
        if row is None:
            row = Profile(id=uuid.uuid4(), email=normalised)
            self.session.add(row)
        row.role = UserRole.ADMIN
        row.full_name = full_name
        row.is_active = True
        await self.session.flush()
        self._count("admins", 1)
        logger.info("admin_role_granted", email=normalised, profile_id=str(row.id))


def _title_from_slug(slug: str) -> str:
    """`first-aid` -> `First Aid`."""
    special = {
        "msds": "MSDS",
        "ppe": "PPE",
        "5s": "5S",
        "iso7010": "ISO 7010",
        "5min": "5 min",
        "ghs": "GHS",
        "copq": "COPQ",
        "3r": "3R",
        "hd": "HD",
    }
    words = []
    for part in slug.split("-"):
        words.append(special.get(part, part.capitalize()))
    return " ".join(words)


def _sku_token(value: str) -> str:
    """`3MM ACP` -> `3MMACP`. Keeps SKUs filesystem- and URL-safe."""
    return "".join(ch for ch in value.upper() if ch.isalnum())


async def _reset(session: AsyncSession) -> None:
    """Remove catalogue and content rows so the seed rebuilds from scratch.

    Deliberately does **not** touch profiles, orders, payments or audit logs. A
    reset that silently deleted real orders would be a catastrophe from a
    mistyped flag.
    """
    logger.warning("reset_requested_deleting_catalogue")
    for model in (
        IndustryProduct,
        Industry,
        ProductTag,
        ProductImage,
        InventoryMovement,
        Inventory,
        ProductVariant,
        Product,
        Category,
        Tag,
        Coupon,
        ShippingMethod,
    ):
        await session.execute(delete(model))
    logger.info("reset_complete")


async def run(
    *,
    reset: bool = False,
    admin_email: str | None = None,
    image_dir: Path | None = None,
) -> int:
    settings = get_settings()
    configure_logging(settings)

    target_dir = image_dir or DEFAULT_IMAGE_DIR
    get_engine(settings)

    summary = ""
    async with session_scope() as session:
        if reset:
            await _reset(session)

        seeder = Seeder(session, target_dir)
        await seeder.seed_categories()
        await seeder.seed_tags()
        await seeder.seed_products()
        await seeder.seed_industries()
        await seeder.seed_shipping()
        await seeder.seed_coupons()

        if admin_email:
            await seeder.seed_admin(admin_email)

        await session.execute(
            pg_insert(IdempotentCounter)
            .values(name="order", value=0)
            .on_conflict_do_nothing(index_elements=["name"])
        )
        await session.execute(
            pg_insert(IdempotentCounter)
            .values(name="invoice", value=0)
            .on_conflict_do_nothing(index_elements=["name"])
        )

        summary = ", ".join(f"{key}={value}" for key, value in sorted(seeder.stats.items()))
        logger.info("seed_complete", summary=summary, image_dir=str(target_dir))

    print(f"Seed complete: {summary}", file=sys.stderr)
    print(f"Placeholder artwork: {target_dir}", file=sys.stderr)
    if admin_email:
        print(
            f"\nADMIN granted to {admin_email}.\n"
            "The Supabase auth user must already exist for this profile to be\n"
            "usable. Create it in the Supabase dashboard if it does not.\n",
            file=sys.stderr,
        )
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Seed the storefront database")
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Delete catalogue rows before seeding (never touches orders)",
    )
    parser.add_argument("--admin-email", help="Grant ADMIN to this account")
    parser.add_argument(
        "--image-dir",
        type=Path,
        default=None,
        help=f"Where to write placeholder artwork (default: {DEFAULT_IMAGE_DIR})",
    )
    args = parser.parse_args()
    return asyncio.run(
        run(reset=args.reset, admin_email=args.admin_email, image_dir=args.image_dir)
    )


if __name__ == "__main__":
    raise SystemExit(main())
