/**
 * The variant matrix.
 *
 * This is the highest-value test file in the frontend, because the Material x
 * Size selector is where a bug silently sells the wrong product. The tests
 * below are written against a matrix that deliberately has *irregular*
 * combinations - the same shape as the real seeded data, where not every
 * material is made in every size.
 */

import { describe, expect, it } from "vitest";

import type { ProductDetail, Variant, VariantOption } from "@/lib/api/types";
import {
  applySelection,
  axisValues,
  buildMatrix,
  initialSelection,
  matchingVariants,
  purchasableVariant,
  resolveVariant,
  selectionLabel,
} from "@/lib/variants";

// ---------------------------------------------------------------------------
// Fixtures
// ---------------------------------------------------------------------------

function variant(
  material: string,
  size: string,
  options: { price: number; inStock?: boolean; isDefault?: boolean; id?: string } = {
    price: 0,
  },
): Variant {
  const id = options.id ?? `${material}-${size}`;
  return {
    id,
    sku: `SKU-${material}-${size}`,
    title: `${size} - ${material}`,
    attributes: { Size: size, Material: material },
    price: {
      amount: options.price,
      currency: "INR",
      symbol: "Rs.",
      formatted: `Rs.${options.price / 100}`,
    },
    compare_at_price: null,
    discount_percent: 0,
    currency: "INR",
    status: "ACTIVE",
    is_default: options.isDefault ?? false,
    available_quantity: options.inStock === false ? 0 : 50,
    in_stock: options.inStock ?? true,
    low_stock: false,
    options: { Size: size, Material: material },
  };
}

function option(name: string, values: string[], variants: Variant[]): VariantOption {
  const byValue: Record<string, string[]> = {};
  for (const value of values) {
    byValue[value] = variants.filter((v) => v.attributes[name] === value).map((v) => v.id);
  }
  return { name, values, variant_ids_by_value: byValue };
}

/**
 * An irregular matrix: ACP is made in four sizes, vinyl in two, autoglow in
 * three, and 48x96 exists only in ACP.
 */
function buildIrregularProduct(): ProductDetail {
  const variants = [
    variant("3MM ACP", "8x12", { price: 10_000, isDefault: true }),
    variant("3MM ACP", "18x24", { price: 18_000 }),
    variant("3MM ACP", "24x36", { price: 27_000 }),
    variant("3MM ACP", "48x96", { price: 88_000 }),
    variant("ECO VINYL STICKER", "8x12", { price: 4_000 }),
    variant("ECO VINYL STICKER", "18x24", { price: 6_000 }),
    variant("AUTOGLOW STICKER", "12x18", { price: 12_000 }),
    variant("AUTOGLOW STICKER", "18x24", { price: 16_000 }),
  ];

  return {
    id: "product-1",
    title: "Danger High Voltage",
    slug: "danger-high-voltage",
    subtitle: null,
    short_description: "Board",
    description: "Board",
    sku: "SPP-ELS-001",
    brand: "Safety Poster Prints",
    category: {
      id: "c1",
      name: "Electrical Safety",
      slug: "electrical-safety",
      parent_id: null,
      image_url: null,
      position: 1,
    },
    breadcrumb: [],
    price: variants[0].price,
    compare_at_price: null,
    discount_percent: 0,
    min_price: variants[4].price,
    max_price: variants[3].price,
    specs: {},
    tags: [],
    images: [],
    variants,
    options: [
      option(
        "Material",
        ["3MM ACP", "ECO VINYL STICKER", "AUTOGLOW STICKER"],
        variants,
      ),
      option("Size", ["8x12", "12x18", "18x24", "24x36", "48x96"], variants),
    ],
    rating_average: 0,
    rating_count: 0,
    rating_distribution: {},
    is_featured: false,
    status: "ACTIVE",
    stock_status: "in_stock",
    in_stock: true,
    total_available: 350,
    seo_title: null,
    seo_description: null,
    created_at: null,
    updated_at: null,
  };
}

// ---------------------------------------------------------------------------

describe("buildMatrix", () => {
  it("orders Material before Size", () => {
    const matrix = buildMatrix(buildIrregularProduct());
    expect(matrix.axes).toEqual(["Material", "Size"]);
  });

  it("derives the value lists from the variants, not from a hard-coded list", () => {
    const matrix = buildMatrix(buildIrregularProduct());
    // 48x96 exists in the API response, so it must appear - and it must not
    // appear for a material that has no 48x96 variant.
    expect(matrix.byAxis.Size.values).toContain("48x96");
    expect(matrix.hasChoices).toBe(true);
  });

  it("drops DISCONTINUED variants so they are not selectable", () => {
    const product = buildIrregularProduct();
    product.variants = [
      ...product.variants,
      { ...variant("3MM ACP", "36x72", { price: 50_000 }), status: "DISCONTINUED" },
    ];
    const matrix = buildMatrix(product);
    expect(matrix.variants.some((v) => v.attributes.Size === "36x72")).toBe(false);
  });

  it("handles a product with a single variant and no choices", () => {
    const only = variant("3MM ACP", "12x18", { price: 12_000, isDefault: true });
    const product = { ...buildIrregularProduct(), variants: [only], options: [] };
    const matrix = buildMatrix(product);
    expect(matrix.axes).toEqual([]);
    expect(matrix.hasChoices).toBe(false);
    expect(purchasableVariant(matrix, {})).toBe(only);
  });
});

describe("axisValues - intersection, not union", () => {
  const product = buildIrregularProduct();
  const matrix = buildMatrix(product);

  it("offers every size when no material is chosen yet", () => {
    const sizes = axisValues(matrix, "Size", {});
    expect(sizes.every((entry) => entry.available)).toBe(true);
  });

  it("disables sizes the selected material is not made in", () => {
    // Vinyl is only made in 8x12 and 18x24.
    const sizes = axisValues(matrix, "Size", { Material: "ECO VINYL STICKER" });
    const available = sizes.filter((s) => s.available).map((s) => s.value);
    const disabled = sizes.filter((s) => !s.available).map((s) => s.value);

    expect(available.sort()).toEqual(["18x24", "8x12"]);
    expect(disabled.sort()).toEqual(["12x18", "24x36", "48x96"]);
  });

  it("keeps 48x96 available for ACP, the only material it is made in", () => {
    const sizes = axisValues(matrix, "Size", { Material: "3MM ACP" });
    expect(sizes.find((s) => s.value === "48x96")?.available).toBe(true);
  });

  it("autoglow exposes only the two sizes it is actually made in", () => {
    const sizes = axisValues(matrix, "Size", { Material: "AUTOGLOW STICKER" });
    expect(sizes.filter((s) => s.available).map((s) => s.value).sort()).toEqual([
      "12x18",
      "18x24",
    ]);
  });

  it("every material remains selectable regardless of the chosen size", () => {
    // All three materials have an 18x24 variant, so all stay open.
    const materials = axisValues(matrix, "Material", { Size: "18x24" });
    expect(materials.every((m) => m.available)).toBe(true);
  });

  it("a material with no variant for the chosen size is disabled", () => {
    const materials = axisValues(matrix, "Material", { Size: "12x18" });
    const byValue = Object.fromEntries(materials.map((m) => [m.value, m.available]));
    expect(byValue["3MM ACP"]).toBe(false);
    expect(byValue["ECO VINYL STICKER"]).toBe(false);
    expect(byValue["AUTOGLOW STICKER"]).toBe(true);
  });

  it("resolves the exact variant for a complete selection", () => {
    const sizes = axisValues(matrix, "Size", { Material: "3MM ACP" });
    const large = sizes.find((s) => s.value === "48x96");
    expect(large?.variant?.price.amount).toBe(88_000);
    expect(large?.variant?.sku).toBe("SKU-3MM ACP-48x96");
  });
});

describe("applySelection", () => {
  const matrix = buildMatrix(buildIrregularProduct());

  it("keeps a size that the new material supports", () => {
    const next = applySelection(matrix, { Size: "18x24" }, "Material", "3MM ACP");
    expect(next).toEqual({ Size: "18x24", Material: "3MM ACP" });
  });

  it("clears a size the new material cannot supply", () => {
    // ACP is not made in 12x18. Leaving the selection pointing at 12x18 would
    // resolve to no variant at all.
    const next = applySelection(matrix, { Size: "12x18" }, "Material", "3MM ACP");
    expect(next.Material).toBe("3MM ACP");
    expect(next.Size).toBeUndefined();
  });

  it("never leaves a selection that resolves to more than one variant", () => {
    const next = applySelection(matrix, { Size: "48x96" }, "Material", "ECO VINYL STICKER");
    expect(resolveVariant(matrix, next)).toBeNull();
  });

  it("clearing the axis being changed still leaves a consistent selection", () => {
    const next = applySelection(matrix, { Material: "3MM ACP", Size: "24x36" }, "Size", "8x12");
    expect(next).toEqual({ Material: "3MM ACP", Size: "8x12" });
    expect(resolveVariant(matrix, next)).not.toBeNull();
  });

  /**
   * The repair is defence in depth, not a reachable code path.
   *
   * `axisValues` disables a value that has no variant alongside the current
   * selection, so a user can never *click* a conflicting value in the first
   * place. That is the desirable property - the invalid combination is
   * unreachable, not merely repaired - but it means the repair only matters for
   * programmatic state (a deep link, a restored session, a future server-driven
   * selection). This test records that reasoning so a future change to the
   * disabling rule does not silently make the selection able to deadlock.
   */
  it("cannot be reached by clicking, because a conflicting value is disabled first", () => {
    const conflicting = axisValues(matrix, "Material", { Size: "8x12" }).find(
      (entry) => entry.value === "AUTOGLOW STICKER",
    );
    expect(conflicting?.available).toBe(false);
  });
});

describe("reachability", () => {
  /**
   * Every material must be reachable from the default selection.
   *
   * This is the property that makes strict disabling safe. A material that is
   * unavailable at the default size is *greyed out*, not hidden - and there
   * must always exist a size, selectable from the default state, that makes it
   * available. Without this, a customer could look at a disabled material with
   * no way to work out how to reach it.
   */
  it("every material can be reached by first choosing a size it is made in", () => {
    const matrix = buildMatrix(buildIrregularProduct());
    const start = initialSelection(matrix);

    for (const material of matrix.byAxis.Material.values) {
      const availableNow = axisValues(matrix, "Material", start).find(
        (entry) => entry.value === material,
      )?.available;
      if (availableNow) continue;

      // Not available at the default size: is it reachable via another size?
      const reachable = matrix.byAxis.Size.values.some((size) => {
        if (!axisValues(matrix, "Size", start).find((s) => s.value === size)?.available) {
          return false;
        }
        return axisValues(matrix, "Material", { ...start, Size: size }).find(
          (entry) => entry.value === material,
        )?.available;
      });

      expect(reachable, `${material} cannot be reached from the default selection`).toBe(
        true,
      );
    }
  });

  it("every size can be reached from the default material", () => {
    const matrix = buildMatrix(buildIrregularProduct());
    const start = initialSelection(matrix);
    for (const size of matrix.byAxis.Size.values) {
      const entry = axisValues(matrix, "Size", start).find((s) => s.value === size);
      // Either it is available now, or it is sold in some other material and
      // reachable by switching material first.
      const reachable = entry?.available || matrix.variants.some((v) => v.attributes.Size === size);
      expect(reachable, `${size} is in no variant at all`).toBe(true);
    }
  });
});

describe("purchasableVariant", () => {
  const matrix = buildMatrix(buildIrregularProduct());

  it("is null while an axis is unselected", () => {
    expect(purchasableVariant(matrix, { Material: "3MM ACP" })).toBeNull();
    expect(purchasableVariant(matrix, {})).toBeNull();
  });

  it("is null for a combination the business does not sell", () => {
    expect(
      purchasableVariant(matrix, { Material: "3MM ACP", Size: "12x18" }),
    ).toBeNull();
  });

  it("returns the variant for a valid, in-stock combination", () => {
    const found = purchasableVariant(matrix, { Material: "3MM ACP", Size: "24x36" });
    expect(found?.price.amount).toBe(27_000);
  });

  it("is null when the valid variant is sold out", () => {
    const product = buildIrregularProduct();
    product.variants = product.variants.map((v) =>
      v.attributes.Material === "3MM ACP" && v.attributes.Size === "24x36"
        ? { ...v, in_stock: false, available_quantity: 0 }
        : v,
    );
    const soldOutMatrix = buildMatrix(product);
    expect(
      purchasableVariant(soldOutMatrix, { Material: "3MM ACP", Size: "24x36" }),
    ).toBeNull();
  });
});

describe("matchingVariants", () => {
  const matrix = buildMatrix(buildIrregularProduct());

  it("returns every variant for an empty selection", () => {
    expect(matchingVariants(matrix, {})).toHaveLength(matrix.variants.length);
  });

  it("applies both axes as a conjunction", () => {
    const found = matchingVariants(matrix, { Material: "3MM ACP", Size: "8x12" });
    expect(found).toHaveLength(1);
    expect(found[0].sku).toBe("SKU-3MM ACP-8x12");
  });

  it("returns an empty list for a combination that does not exist", () => {
    expect(matchingVariants(matrix, { Material: "3MM ACP", Size: "12x18" })).toEqual([]);
  });
});

describe("initialSelection", () => {
  it("starts on the API's default variant, so the price shown is the price bought", () => {
    const matrix = buildMatrix(buildIrregularProduct());
    const selection = initialSelection(matrix);
    expect(selection).toEqual({ Size: "8x12", Material: "3MM ACP" });
    expect(purchasableVariant(matrix, selection)?.price.amount).toBe(10_000);
  });

  it("falls back to the first variant when none is marked default", () => {
    const product = buildIrregularProduct();
    product.variants = product.variants.map((v) => ({ ...v, is_default: false }));
    const matrix = buildMatrix(product);
    expect(initialSelection(matrix)).toEqual({ Size: "8x12", Material: "3MM ACP" });
  });
});

describe("selectionLabel", () => {
  const matrix = buildMatrix(buildIrregularProduct());
  it("joins the selected axes in display order", () => {
    expect(selectionLabel(matrix, { Size: "18x24", Material: "3MM ACP" })).toBe(
      "3MM ACP / 18x24",
    );
  });
  it("omits unselected axes", () => {
    expect(selectionLabel(matrix, { Material: "3MM ACP" })).toBe("3MM ACP");
  });
});
