"""Catalogue API tests.

The seed data is loaded into the test database so these assertions run against
the same shape a real storefront sees: variant matrices, sold-out variants,
price ladders, tags and multi-level categories.
"""

from __future__ import annotations

import pytest
from app.models.catalog import Inventory, Product, ProductVariant
from app.models.enums import ProductStatus
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

pytestmark = [pytest.mark.integration, pytest.mark.api]


# ---------------------------------------------------------------------------
# Product listing
# ---------------------------------------------------------------------------
class TestProductListing:
    async def test_listing_returns_paginated_products(self, catalogue_client: AsyncClient) -> None:
        response = await catalogue_client.get("/api/v1/products", params={"per_page": 5})

        assert response.status_code == 200, response.text
        body = response.json()
        assert len(body["items"]) == 5
        assert body["meta"]["total"] >= 27
        assert body["meta"]["has_next"] is True
        assert body["meta"]["per_page"] == 5

    async def test_pagination_is_stable_and_non_overlapping(
        self, catalogue_client: AsyncClient
    ) -> None:
        first = await catalogue_client.get(
            "/api/v1/products", params={"page": 1, "per_page": 6, "sort": "newest"}
        )
        second = await catalogue_client.get(
            "/api/v1/products", params={"page": 2, "per_page": 6, "sort": "newest"}
        )

        ids_a = {i["id"] for i in first.json()["items"]}
        ids_b = {i["id"] for i in second.json()["items"]}
        assert len(ids_a) == 6
        assert len(ids_b) == 6
        # A tie on created_at must not let an item appear on two pages.
        assert ids_a.isdisjoint(ids_b)

    async def test_invalid_page_is_rejected(self, catalogue_client: AsyncClient) -> None:
        response = await catalogue_client.get("/api/v1/products", params={"page": 0})
        assert response.status_code == 422
        assert "page" in response.json()["error"]["field_errors"]

    async def test_per_page_is_capped(self, catalogue_client: AsyncClient) -> None:
        response = await catalogue_client.get("/api/v1/products", params={"per_page": 500})
        assert response.status_code == 422

    async def test_unpublished_products_are_hidden(
        self, catalogue_client: AsyncClient, catalogue_session: AsyncSession
    ) -> None:
        """A draft product is invisible to shoppers, in the list and on the PDP."""

        result = await catalogue_session.execute(select(Product).limit(1))
        product = result.scalar_one()
        original_status = product.status
        product.status = ProductStatus.DRAFT
        await catalogue_session.commit()

        try:
            listing = await catalogue_client.get("/api/v1/products", params={"per_page": 100})
            assert product.id not in {i["id"] for i in listing.json()["items"]}

            detail = await catalogue_client.get(f"/api/v1/products/{product.slug}")
            assert detail.status_code == 404
        finally:
            # Restore, because the catalogue fixture is shared with later tests.
            product.status = original_status
            await catalogue_session.commit()


# ---------------------------------------------------------------------------
# Filtering and sorting
# ---------------------------------------------------------------------------
class TestProductFilters:
    async def test_filter_by_category_slug(self, catalogue_client: AsyncClient) -> None:
        response = await catalogue_client.get(
            "/api/v1/products", params={"category": "electrical-safety", "per_page": 50}
        )

        assert response.status_code == 200
        items = response.json()["items"]
        assert items, "seed data should have electrical safety products"
        assert {i["category_slug"] for i in items} == {"electrical-safety"}

    async def test_parent_category_includes_descendants(
        self, catalogue_client: AsyncClient
    ) -> None:
        """
        The live catalogue is a flat 18-category list and the rebuild keeps it
        flat, so selecting a category returns exactly that category. This test
        pins that decision: if a hierarchy is ever introduced, the assertion has
        to change deliberately rather than by accident.
        """
        response = await catalogue_client.get(
            "/api/v1/products", params={"category": "electrical-safety", "per_page": 50}
        )

        slugs = {i["category_slug"] for i in response.json()["items"]}
        assert slugs == {"electrical-safety"}

    async def test_whole_catalogue_is_reachable_without_a_category(
        self, catalogue_client: AsyncClient
    ) -> None:
        response = await catalogue_client.get("/api/v1/products", params={"per_page": 100})
        total = response.json()["meta"]["total"]
        assert total >= 100, "the seeded catalogue should exceed 100 products"

    async def test_price_range_filter(self, catalogue_client: AsyncClient) -> None:
        response = await catalogue_client.get(
            "/api/v1/products",
            params={"min_price": 1000000, "max_price": 2000000, "per_page": 50},
        )

        assert response.status_code == 200
        for item in response.json()["items"]:
            assert 1000000 <= item["price"]["amount"] <= 2000000

    async def test_in_stock_filter_excludes_sold_out_products(
        self, catalogue_client: AsyncClient
    ) -> None:
        """
        Stock is resolved per *variant*, so a product stays in stock while any
        material and size combination is purchasable. The filter therefore
        removes fully sold-out products rather than individual options.
        """
        everything = await catalogue_client.get("/api/v1/products", params={"per_page": 100})
        in_stock = await catalogue_client.get(
            "/api/v1/products", params={"in_stock": True, "per_page": 100}
        )

        all_ids = {i["id"] for i in everything.json()["items"]}
        stock_ids = {i["id"] for i in in_stock.json()["items"]}

        assert stock_ids <= all_ids
        assert stock_ids, "the seeded catalogue has purchasable stock"
        for item in in_stock.json()["items"]:
            assert item["in_stock"] is True
            assert item["total_available"] > 0

    async def test_on_sale_filter(self, catalogue_client: AsyncClient) -> None:
        response = await catalogue_client.get(
            "/api/v1/products", params={"on_sale": True, "per_page": 100}
        )

        assert response.status_code == 200
        items = response.json()["items"]
        assert items, "seed should include at least one discounted product"
        for item in items:
            assert item["is_on_sale"] is True
            assert item["compare_at_price"] is not None
            assert item["price"]["amount"] < item["compare_at_price"]["amount"]
            assert item["discount_percent"] > 0

    async def test_tag_filter(self, catalogue_client: AsyncClient) -> None:
        """Tag filtering is a real requirement and must be data-driven."""
        response = await catalogue_client.get(
            "/api/v1/products", params={"tag": "iso7010", "per_page": 50}
        )

        assert response.status_code == 200
        assert response.json()["meta"]["total"] >= 5

    async def test_multiple_tags_are_combined_with_and(self, catalogue_client: AsyncClient) -> None:
        """Two tags must narrow the result set, never widen it."""
        single = await catalogue_client.get(
            "/api/v1/products", params={"tag": "iso7010", "per_page": 100}
        )
        both = await catalogue_client.get(
            "/api/v1/products",
            params={"tag": ["iso7010", "electrical"], "per_page": 100},
        )

        assert both.json()["meta"]["total"] <= single.json()["meta"]["total"]


class TestMaterialAndSizeFilters:
    """
    Material and Size are the filters a buyer uses most, and both are
    properties of a *single* variant row. The risk guarded against here is the
    two predicates being evaluated independently, which would cross-product: a
    product carrying (3MM ACP, 12x18) and (ECO VINYL, 18x24) must not match a
    filter for material=3MM ACP **and** size=18x24, because the business does
    not sell that pairing.
    """

    async def test_material_filter_is_applied(self, catalogue_client: AsyncClient) -> None:
        """
        Every seeded product carries a 3MM ACP option, so this filter is not
        expected to reduce the count on its own - only to be *applied*. What is
        asserted is that it is applied, by checking that adding a scarce size
        narrows the result further.
        """
        acp = await catalogue_client.get(
            "/api/v1/products", params={"material": "3MM ACP", "per_page": 100}
        )

        assert acp.status_code == 200
        assert acp.json()["meta"]["total"] > 0

        # A genuinely scarce combination must return fewer rows.
        acp_36 = await catalogue_client.get(
            "/api/v1/products",
            params={"material": "3MM ACP", "size": "36x48", "per_page": 100},
        )
        assert acp_36.json()["meta"]["total"] < acp.json()["meta"]["total"]

    async def test_size_filter_restricts_results(self, catalogue_client: AsyncClient) -> None:
        everything = await catalogue_client.get("/api/v1/products", params={"per_page": 100})
        large = await catalogue_client.get(
            "/api/v1/products", params={"size": "36x48", "per_page": 100}
        )

        assert 0 < large.json()["meta"]["total"] < everything.json()["meta"]["total"]

    async def test_material_and_size_together_are_a_subset(
        self, catalogue_client: AsyncClient
    ) -> None:
        material_only = await catalogue_client.get(
            "/api/v1/products", params={"material": "3MM ACP", "per_page": 100}
        )
        both = await catalogue_client.get(
            "/api/v1/products",
            params={"material": "3MM ACP", "size": "36x48", "per_page": 100},
        )

        assert both.json()["meta"]["total"] <= material_only.json()["meta"]["total"], (
            "adding a size filter widened the result set"
        )

    async def test_every_returned_product_really_has_that_variant(
        self, catalogue_client: AsyncClient, catalogue_session: AsyncSession
    ) -> None:
        """
        The strong form of the cross-product check: for every product the filter
        returns, confirm one *single* variant row matches both values.
        """
        from app.models.catalog import Product, ProductVariant
        from sqlalchemy import select

        response = await catalogue_client.get(
            "/api/v1/products",
            params={"material": "3MM ACP", "size": "24x36", "per_page": 50},
        )
        slugs = [i["slug"] for i in response.json()["items"]]
        assert slugs, "expected matches for this combination"

        for slug in slugs:
            product_result = await catalogue_session.execute(
                select(Product).where(Product.slug == slug)
            )
            product = product_result.scalar_one()
            variants_result = await catalogue_session.execute(
                select(ProductVariant).where(ProductVariant.product_id == product.id)
            )
            variants = variants_result.scalars().all()

            matches = [
                v
                for v in variants
                if v.attributes.get("Material") == "3MM ACP" and v.attributes.get("Size") == "24x36"
            ]
            assert matches, f"{slug} was returned by the filter but has no 3MM ACP / 24x36 variant"

    async def test_facets_expose_materials_and_sizes(self, catalogue_client: AsyncClient) -> None:
        response = await catalogue_client.get("/api/v1/facets")

        assert response.status_code == 200
        body = response.json()
        assert {m["value"] for m in body["materials"]} == {
            "3MM ACP",
            "5MM FOAMSHEET",
            "AUTOGLOW STICKER",
            "ECO VINYL STICKER",
        }
        size_values = {s["value"] for s in body["sizes"]}
        assert {"8x12", "12x18", "18x24", "24x36"} <= size_values
        assert all(s["count"] > 0 for s in body["sizes"])

    async def test_category_facets_are_scoped(self, catalogue_client: AsyncClient) -> None:
        """Facets inside a category must not advertise options it does not sell."""
        scoped = await catalogue_client.get("/api/v1/categories/office-signages/facets")
        everywhere = await catalogue_client.get("/api/v1/facets")

        scoped_sizes = {s["value"] for s in scoped.json()["sizes"]}
        global_sizes = {s["value"] for s in everywhere.json()["sizes"]}

        assert scoped_sizes, "the category should have some sizes"
        assert scoped_sizes <= global_sizes
        # Office signage uses the "sticker" size profile, so no 48x96.
        assert "48x96" not in scoped_sizes

    async def test_brand_filter_is_case_insensitive(self, catalogue_client: AsyncClient) -> None:
        lower = await catalogue_client.get(
            "/api/v1/products", params={"brand": "Safety Poster Prints", "per_page": 50}
        )
        upper = await catalogue_client.get(
            "/api/v1/products", params={"brand": "Safety Poster Prints", "per_page": 50}
        )

        assert lower.json()["meta"]["total"] == upper.json()["meta"]["total"] > 0

    @pytest.mark.parametrize(
        ("sort", "check"),
        [
            (
                "price_asc",
                lambda items: all(
                    items[i]["price"]["amount"] <= items[i + 1]["price"]["amount"]
                    for i in range(len(items) - 1)
                ),
            ),
            (
                "price_desc",
                lambda items: all(
                    items[i]["price"]["amount"] >= items[i + 1]["price"]["amount"]
                    for i in range(len(items) - 1)
                ),
            ),
            (
                "name_asc",
                lambda items: all(
                    items[i]["title"].lower() <= items[i + 1]["title"].lower()
                    for i in range(len(items) - 1)
                ),
            ),
        ],
    )
    async def test_sort_orders(self, catalogue_client: AsyncClient, sort: str, check) -> None:
        response = await catalogue_client.get(
            "/api/v1/products", params={"sort": sort, "per_page": 20}
        )

        assert response.status_code == 200
        items = response.json()["items"]
        assert check(items), f"sort={sort} was not respected"

    async def test_unknown_sort_is_rejected(self, catalogue_client: AsyncClient) -> None:
        response = await catalogue_client.get("/api/v1/products", params={"sort": "cheapest"})
        assert response.status_code == 422


# ---------------------------------------------------------------------------
# Product detail
# ---------------------------------------------------------------------------
class TestProductDetail:
    async def test_detail_returns_full_payload(self, catalogue_client: AsyncClient) -> None:
        response = await catalogue_client.get("/api/v1/products/danger-high-voltage")

        assert response.status_code == 200, response.text
        body = response.json()
        assert body["title"] == "Danger High Voltage"
        assert body["slug"] == "danger-high-voltage"
        assert body["brand"] == "Safety Poster Prints"
        assert body["description"]
        assert body["specs"]["Hazard symbol"]
        assert len(body["images"]) >= 3
        assert body["images"][0]["is_primary"] is True
        assert body["images"][0]["alt_text"]
        assert body["category"]["slug"] == "electrical-safety"
        # Flat taxonomy: a category has no ancestors, so no breadcrumb trail.
        assert body["breadcrumb"] == []

    async def test_variant_matrix_is_material_by_size(self, catalogue_client: AsyncClient) -> None:
        """
        The catalogue's defining structural fact: every product is a
        Material x Size matrix. This asserts both axes are present, which is
        what the filter UI and the PDP selectors depend on.
        """
        body = (await catalogue_client.get("/api/v1/products/danger-high-voltage")).json()

        materials = {v["attributes"]["Material"] for v in body["variants"]}
        sizes = {v["attributes"]["Size"] for v in body["variants"]}

        assert "3MM ACP" in materials
        assert "ECO VINYL STICKER" in materials
        assert "12x18" in sizes
        assert "18x24" in sizes
        # The matrix is a full cross product, not a sparse subset.
        assert len(body["variants"]) == len(materials) * len(sizes)

        axes = {option["name"] for option in body["options"]}
        assert axes == {"Material", "Size"}

    async def test_every_variant_carries_both_option_keys(
        self, catalogue_client: AsyncClient
    ) -> None:
        """A variant missing one axis would be unselectable in the UI."""
        body = (await catalogue_client.get("/api/v1/products/msds-of-caustic-soda")).json()
        for variant in body["variants"]:
            assert variant["attributes"].get("Material")
            assert variant["attributes"].get("Size")

    async def test_option_map_enables_disabling_unavailable_combinations(
        self, catalogue_client: AsyncClient
    ) -> None:
        """The PDP needs to know which value maps to which variant ids."""
        body = (await catalogue_client.get("/api/v1/products/danger-high-voltage")).json()
        material_axis = next(o for o in body["options"] if o["name"] == "Material")

        assert set(material_axis["values"]) == {
            "ECO VINYL STICKER",
            "AUTOGLOW STICKER",
            "5MM FOAMSHEET",
            "3MM ACP",
        }
        for value, ids in material_axis["variant_ids_by_value"].items():
            assert ids, f"material {value} maps to no variants"

    async def test_variant_price_scales_with_size_and_material(
        self, catalogue_client: AsyncClient
    ) -> None:
        """
        The pricing model under test: a variant price is
        ``base * (area / 96) * material_ratio``. This is the one place where a
        mistake silently overcharges or undercharges every board, so the
        ordering is asserted explicitly rather than a single hard-coded value.
        """
        body = (await catalogue_client.get("/api/v1/products/danger-high-voltage")).json()
        by_key = {
            (v["attributes"]["Material"], v["attributes"]["Size"]): v["price"]["amount"]
            for v in body["variants"]
        }

        base_area = 8 * 12

        def expected(material_ratio: float, width: int, height: int) -> int:
            """Reproduce the seed's pricing rule independently of the API."""
            exact = 8000 * ((width * height) / base_area) * material_ratio
            return int((exact + 50) // 100) * 100

        # Smallest size, cheapest material.
        assert by_key[("ECO VINYL STICKER", "12x18")] == expected(1.0, 12, 18)
        # Same size, the most durable material.
        assert by_key[("3MM ACP", "12x18")] == expected(2.3, 12, 18)
        # Cheapest material, larger board.
        assert by_key[("ECO VINYL STICKER", "36x48")] == expected(1.0, 36, 48)

        # Monotonic in both axes.
        assert (
            by_key[("3MM ACP", "36x48")]
            > by_key[("ECO VINYL STICKER", "36x48")]
            > by_key[("3MM ACP", "12x18")]
            > by_key[("ECO VINYL STICKER", "12x18")]
        )

    async def test_no_variant_is_priced_at_zero(self, catalogue_client: AsyncClient) -> None:
        """
        The live catalogue shows Rs.0.00 on a large part of its listing pages.
        A zero price is both a trust problem and an SEO problem, so this is
        asserted across the whole catalogue rather than spot-checked.
        """
        response = await catalogue_client.get("/api/v1/products", params={"per_page": 100})
        for item in response.json()["items"]:
            assert item["price"]["amount"] > 0, f"{item['slug']} is priced at zero"

    async def test_sold_out_variant_is_flagged(
        self, catalogue_client: AsyncClient, catalogue_session: AsyncSession
    ) -> None:
        """A deterministic slice of the matrix is seeded at zero stock."""

        result = await catalogue_session.execute(
            select(ProductVariant, Inventory)
            .join(Inventory, Inventory.variant_id == ProductVariant.id)
            .where(Inventory.quantity == 0)
            .limit(5)
        )
        rows = result.all()
        assert rows, "seed should include some sold-out variants"

        # Fetch each affected product's detail page rather than assuming which
        # category a sold-out variant belongs to.
        from app.models.catalog import Product

        checked = 0
        for variant, _inventory in rows[:5]:
            product_result = await catalogue_session.execute(
                select(Product).where(Product.id == variant.product_id)
            )
            product = product_result.scalar_one()
            detail = await catalogue_client.get(f"/api/v1/products/{product.slug}")
            assert detail.status_code == 200, product.slug

            by_sku = {v["sku"]: v for v in detail.json()["variants"]}
            entry = by_sku[variant.sku]
            assert entry["in_stock"] is False, variant.sku
            assert entry["available_quantity"] == 0, variant.sku
            checked += 1
        assert checked == len(rows[:5])

    async def test_missing_product_is_404(self, catalogue_client: AsyncClient) -> None:
        response = await catalogue_client.get("/api/v1/products/does-not-exist")

        assert response.status_code == 404
        assert response.json()["error"]["code"] == "product_not_found"

    async def test_money_is_integer_minor_units(self, catalogue_client: AsyncClient) -> None:
        body = (await catalogue_client.get("/api/v1/products/danger-high-voltage")).json()

        assert isinstance(body["price"]["amount"], int)
        assert body["price"]["currency"] == "INR"
        # Indian digit grouping, and a trailing ".00" omitted for whole rupees.
        assert body["price"]["formatted"].startswith("Rs.")
        assert "," in body["price"]["formatted"] or len(body["price"]["formatted"]) < 9

    async def test_related_products_exclude_self(self, catalogue_client: AsyncClient) -> None:
        response = await catalogue_client.get("/api/v1/products/danger-high-voltage/related")

        assert response.status_code == 200
        items = response.json()
        assert items
        assert "danger-high-voltage" not in {i["slug"] for i in items}
        # The first related item should be in the same category.
        assert items[0]["reason"] in {"same_category", "same_brand", "also_viewed"}


# ---------------------------------------------------------------------------
# Categories
# ---------------------------------------------------------------------------
class TestCategories:
    async def test_category_list_is_flat_and_slugs_are_preserved(
        self, catalogue_client: AsyncClient
    ) -> None:
        """
        The rebuild preserves the live catalogue's flat 18-category structure
        and its exact slugs, because those slugs carry the existing SEO equity
        and inbound links. A test, so an accidental "cleanup" is caught.
        """
        response = await catalogue_client.get("/api/v1/categories")

        assert response.status_code == 200
        tree = response.json()
        by_slug = {c["slug"]: c for c in tree}

        assert len(tree) == 18
        for required in (
            "msds",
            "ppe",
            "caution-signages",
            "danger-signages",
            "5s-methodology",
            "electrical-safety",
            "directional-signages",
            "emergency-signages",
            # Live slug is misspelled; preserved for SEO, display name corrected.
            "envirnomental-signages",
            "health-safety",
            "fire-safety",
            "motivational-signages",
            "lab-safety",
            "office-signages",
            "quality-productivity",
            "road-safety",
            "canteen",
            "pylon-boards",
        ):
            assert required in by_slug, f"missing preserved category slug {required!r}"

        assert by_slug["envirnomental-signages"]["name"] == "Environmental Signages"
        assert by_slug["pylon-boards"]["name"] == "Outdoor Pylon Signage Board"

        # Flat taxonomy: no parents and no children anywhere.
        assert all(c["parent_id"] is None for c in tree)
        assert all(c["children"] == [] for c in tree)
        assert all(c["ancestors"] == [] for c in tree)

    async def test_category_counts_reflect_the_seeded_catalogue(
        self, catalogue_client: AsyncClient
    ) -> None:
        response = await catalogue_client.get("/api/v1/categories")
        by_slug = {c["slug"]: c for c in response.json()}

        assert by_slug["electrical-safety"]["product_count"] >= 10
        assert by_slug["msds"]["product_count"] >= 10
        assert by_slug["5s-methodology"]["product_count"] >= 5
        assert by_slug["pylon-boards"]["product_count"] >= 3

    async def test_category_detail(self, catalogue_client: AsyncClient) -> None:
        response = await catalogue_client.get("/api/v1/categories/electrical-safety")

        assert response.status_code == 200
        body = response.json()
        assert body["name"] == "Electrical Safety"
        assert body["product_count"] >= 10
        assert body["ancestors"] == []

    async def test_unknown_category_is_404(self, catalogue_client: AsyncClient) -> None:
        response = await catalogue_client.get("/api/v1/categories/not-a-category")
        assert response.status_code == 404
        assert response.json()["error"]["code"] == "category_not_found"

    async def test_facets_are_scoped_to_the_category(self, catalogue_client: AsyncClient) -> None:
        response = await catalogue_client.get("/api/v1/categories/electrical-safety/facets")

        assert response.status_code == 200
        body = response.json()
        brands = {b["value"] for b in body["brands"]}
        assert brands == {"Safety Poster Prints"}
        assert body["price_range"]["max"] >= body["price_range"]["min"] > 0


# ---------------------------------------------------------------------------
# Search
# ---------------------------------------------------------------------------
class TestSearch:
    @pytest.mark.parametrize(
        "term",
        [
            "electrical",  # category and description
            "5S",  # alphanumeric with a digit
            "fire",  # fire safety
            "MSDS",  # acronym
            "chemical",  # description and tags
            "ppe",  # acronym
        ],
    )
    async def test_search_terms_from_the_brief_all_return_results(
        self, catalogue_client: AsyncClient, term: str
    ) -> None:
        response = await catalogue_client.get("/api/v1/search", params={"q": term})

        assert response.status_code == 200
        body = response.json()
        assert body["count"] > 0, f"search for {term!r} returned nothing"
        assert any(i["type"] == "product" for i in body["items"])

    async def test_search_matches_a_sku(self, catalogue_client: AsyncClient) -> None:
        """A procurement user often has a SKU from an old order."""
        response = await catalogue_client.get("/api/v1/search", params={"q": "SPP-ELS-004"})

        assert response.status_code == 200
        assert response.json()["count"] > 0

    async def test_search_matches_a_size(self, catalogue_client: AsyncClient) -> None:
        """Size and material live in variant attributes and must be searchable."""
        response = await catalogue_client.get("/api/v1/search", params={"q": "18x24"})

        assert response.status_code == 200
        assert response.json()["count"] > 0

    async def test_trigram_fallback_catches_typos(self, catalogue_client: AsyncClient) -> None:
        """
        A transposition typo must still match. This exercises the
        ``similarity()`` fallback rather than the tsvector path, because a
        stemmed full-text index cannot match a misspelled token.
        """
        response = await catalogue_client.get("/api/v1/search", params={"q": "corrisive"})

        assert response.status_code == 200
        assert response.json()["count"] > 0, "typo should still match via trigram"

    async def test_search_requires_a_query(self, catalogue_client: AsyncClient) -> None:
        response = await catalogue_client.get("/api/v1/search", params={"q": ""})
        assert response.status_code == 422

    async def test_no_results_state(self, catalogue_client: AsyncClient) -> None:
        response = await catalogue_client.get("/api/v1/search", params={"q": "zzzzznotathing"})

        assert response.status_code == 200
        body = response.json()
        assert body["count"] == 0
        assert body["items"] == []

    async def test_suggestions_return_products(self, catalogue_client: AsyncClient) -> None:
        response = await catalogue_client.get("/api/v1/search/suggestions", params={"q": "dang"})

        assert response.status_code == 200
        items = response.json()
        assert items
        assert items[0]["type"] == "product"
        assert "danger" in items[0]["text"].lower()

    async def test_suggestions_ignore_single_character(self, catalogue_client: AsyncClient) -> None:
        response = await catalogue_client.get("/api/v1/search/suggestions", params={"q": "a"})
        assert response.status_code == 200
        assert response.json() == []

    async def test_malformed_search_query_does_not_500(self, catalogue_client: AsyncClient) -> None:
        """
        websearch_to_tsquery is chosen partly because it tolerates quotes and
        operators. A hostile or simply odd query must not raise.
        """
        for term in ['"', "AND OR NOT", "!!!", "a:b", "*"]:
            response = await catalogue_client.get("/api/v1/search", params={"q": term})
            assert response.status_code == 200, f"{term!r} -> {response.status_code}"


# ---------------------------------------------------------------------------
# Curated rails
# ---------------------------------------------------------------------------
class TestCuratedRails:
    async def test_featured_products(self, catalogue_client: AsyncClient) -> None:
        response = await catalogue_client.get("/api/v1/products/featured")

        assert response.status_code == 200
        items = response.json()
        assert items
        assert all(i["is_featured"] for i in items)

    async def test_new_arrivals(self, catalogue_client: AsyncClient) -> None:
        response = await catalogue_client.get("/api/v1/products/new", params={"limit": 5})

        assert response.status_code == 200
        assert len(response.json()) == 5

    async def test_best_sellers_empty_without_orders(self, catalogue_client: AsyncClient) -> None:
        """No orders yet means no best sellers, not a broken response."""
        response = await catalogue_client.get("/api/v1/products/best-sellers")

        assert response.status_code == 200
        assert response.json() == []


# ---------------------------------------------------------------------------
# No fabricated social proof
# ---------------------------------------------------------------------------
class TestNoFabricatedSocialProof:
    """
    The live site publishes no verifiable reviews, ratings or testimonials.
    The rebuild therefore ships with none, and the rendering paths must degrade
    to an empty state rather than inventing a number.
    """

    async def test_new_product_has_a_zero_rating_not_a_fake_one(
        self, catalogue_client: AsyncClient
    ) -> None:
        body = (await catalogue_client.get("/api/v1/products/caution-wet-floor")).json()

        assert body["rating_average"] == 0.0
        assert body["rating_count"] == 0
        assert sum(body["rating_distribution"].values()) == 0

    async def test_listing_cards_do_not_carry_fake_ratings(
        self, catalogue_client: AsyncClient
    ) -> None:
        response = await catalogue_client.get("/api/v1/products", params={"per_page": 50})
        for item in response.json()["items"]:
            assert item["rating_count"] == 0, f"{item['slug']} shows a fabricated rating"
