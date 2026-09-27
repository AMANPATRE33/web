"""Validate the seed catalogue before it touches the database.

Catches the exact class of defect found on the live site - duplicate slugs,
duplicate SKUs, orphan categories, products with no variants - so a data problem
surfaces as a clear message here rather than as a constraint violation halfway
through a seed run.
"""

from __future__ import annotations

import sys
from collections import Counter

from app.scripts import seed_data as data

errors: list[str] = []
warnings: list[str] = []


def check() -> int:
    category_slugs = {c.slug for c in data.CATEGORIES}
    material_codes = {m.code for m in data.MATERIALS}
    size_labels = {s.label for s in data.SIZES}

    # --- categories -------------------------------------------------------
    if len(category_slugs) != len(data.CATEGORIES):
        errors.append("duplicate category slugs")
    parent_slugs = {c.parent_slug for c in data.CATEGORIES if c.parent_slug}
    missing_parents = parent_slugs - category_slugs
    if missing_parents:
        errors.append(f"categories reference missing parents: {sorted(missing_parents)}")

    # --- products ---------------------------------------------------------
    for label, values in (
        ("slug", [p.slug for p in data.PRODUCTS]),
        ("sku", [p.sku for p in data.PRODUCTS]),
        ("title", [p.title for p in data.PRODUCTS]),
    ):
        dupes = [v for v, n in Counter(values).items() if n > 1]
        if dupes:
            errors.append(f"duplicate product {label}: {dupes}")

    for product in data.PRODUCTS:
        if product.category_slug not in category_slugs:
            errors.append(f"{product.slug!r}: unknown category {product.category_slug!r}")
        if product.base_price <= 0:
            errors.append(f"{product.slug!r}: base_price must be > 0 (never ship a zero price)")
        if product.compare_at_price is not None and product.compare_at_price < product.base_price:
            errors.append(f"{product.slug!r}: compare_at_price is below base_price")

        for size in product.size_labels or ():
            if size not in size_labels:
                errors.append(f"{product.slug!r}: unknown size {size!r}")
        for code in product.material_codes or ():
            if code not in material_codes:
                errors.append(f"{product.slug!r}: unknown material {code!r}")

    # --- industries -------------------------------------------------------
    product_slugs = {p.slug for p in data.PRODUCTS}
    for industry in data.INDUSTRIES:
        for slug in industry.product_slugs:
            if slug not in product_slugs:
                errors.append(f"industry {industry.slug!r} references unknown product {slug!r}")

    # --- coupons ----------------------------------------------------------
    for coupon in data.COUPONS:
        if coupon.coupon_type == "PERCENTAGE" and not (0 < coupon.value <= 10000):
            errors.append(f"coupon {coupon.code}: percentage out of basis-point range")
        if coupon.coupon_type == "FIXED" and coupon.value <= 0:
            errors.append(f"coupon {coupon.code}: fixed value must be > 0")

    # --- warnings ---------------------------------------------------------
    empty_categories = [
        c.slug for c in data.CATEGORIES if not any(p.category_slug == c.slug for p in data.PRODUCTS)
    ]
    if empty_categories:
        warnings.append(
            f"categories with no seeded products (expected for a partial import): "
            f"{empty_categories}"
        )

    # --- report -----------------------------------------------------------
    variant_total = 0
    for product in data.PRODUCTS:
        sizes = product.size_labels or data.SIZE_PROFILES["poster"]
        materials = product.material_codes or [m.code for m in data.MATERIALS]
        variant_total += len(sizes) * len(materials)

    print(f"categories  {len(data.CATEGORIES)}")
    print(f"products    {len(data.PRODUCTS)}")
    print(f"variants    {variant_total} (derived from size x material)")
    print(f"materials   {len(data.MATERIALS)}")
    print(f"sizes       {len(data.SIZES)}")
    print(f"industries  {len(data.INDUSTRIES)}")
    print(f"coupons     {len(data.COUPONS)}")
    print()

    for warning in warnings:
        print(f"WARN  {warning}")
    for error in errors:
        print(f"ERROR {error}")

    if errors:
        print(f"\n{len(errors)} error(s). Fix before seeding.")
        return 1
    print("Seed data is valid.")
    return 0


if __name__ == "__main__":
    sys.exit(check())
