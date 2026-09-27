/**
 * The variant matrix: resolving a (Material, Size) selection to a variant.
 *
 * This is the heart of the product page and the easiest thing to get subtly
 * wrong, so the rules are stated explicitly:
 *
 *   1. A product's options and their per-value variant ids come from the API.
 *      Nothing is assumed about which materials or sizes exist.
 *   2. Two filters compose as an intersection. A size is selectable only if some
 *      variant carries *both* the chosen material and that size. A product
 *      sold only in ACP and vinyl still offers both, but a size sold in ACP
 *      only disappears once vinyl is selected.
 *   3. Changing one axis must never leave an invalid combination selected. If
 *      the new material has no variant for the chosen size, the size selection
 *      is cleared rather than silently pointing at a nonexistent variant.
 *   4. The resolved variant carries the price, the SKU and the stock. The UI
 *      never derives any of those itself.
 *
 * A pure module, deliberately: it is unit-testable without React or a browser,
 * which is where the real value is.
 */

import type { ProductDetail, Variant, VariantOption } from "./api/types";

/** Which option axis to render first. Material changes the price least. */
export const AXIS_PRIORITY = ["Material", "Size", "Colour", "Color"] as const;

export interface Matrix {
  /** Axis names in display order. */
  axes: string[];
  /** Axis name -> its option descriptor. */
  byAxis: Record<string, VariantOption>;
  variants: Variant[];
  /** True when the product has more than one purchasable option. */
  hasChoices: boolean;
}

export type Selection = Record<string, string>;

export interface AxisValueState {
  value: string;
  /** Selectable given the rest of the current selection. */
  available: boolean;
  /** The variant this value resolves to, when the full selection is valid. */
  variant: Variant | null;
  /** The variant for this value alone, ignoring the other axes. */
  variantForValue: Variant | null;
}

export function buildMatrix(product: ProductDetail): Matrix {
  const variants = (product.variants ?? []).filter((v) => v.status !== "DISCONTINUED");

  const declared = (product.options ?? []).filter(
    (option) => option.values.length > 1 || variants.length > 1,
  );

  // Order axes: known names first in the priority above, then anything else in
  // the order the API returned them.
  const sorted = [...declared].sort((a, b) => {
    const ai = AXIS_PRIORITY.indexOf(a.name as (typeof AXIS_PRIORITY)[number]);
    const bi = AXIS_PRIORITY.indexOf(b.name as (typeof AXIS_PRIORITY)[number]);
    const rank = (v: number) => (v === -1 ? 99 : v);
    return rank(ai) - rank(bi) || a.name.localeCompare(b.name);
  });

  const byAxis: Record<string, VariantOption> = {};
  for (const option of sorted) byAxis[option.name] = option;

  return {
    axes: sorted.map((option) => option.name),
    byAxis,
    variants,
    hasChoices: sorted.length > 0 && variants.length > 1,
  };
}

/** All variants that satisfy every currently-selected axis. */
export function matchingVariants(matrix: Matrix, selection: Selection): Variant[] {
  const active = Object.entries(selection).filter(([, value]) => Boolean(value));
  if (active.length === 0) return matrix.variants;
  return matrix.variants.filter((variant) =>
    active.every(([axis, value]) => variant.attributes?.[axis] === value),
  );
}

/** The single variant for a complete selection, or null if it does not exist. */
export function resolveVariant(matrix: Matrix, selection: Selection): Variant | null {
  const matches = matchingVariants(matrix, selection);
  return matches.length === 1 ? matches[0] : null;
}

/**
 * The state of every value on one axis, given the rest of the selection.
 *
 * This is what disables a Size that the chosen Material is not sold in.
 */
export function axisValues(
  matrix: Matrix,
  axisName: string,
  selection: Selection,
): AxisValueState[] {
  const option = matrix.byAxis[axisName];
  if (!option) return [];

  return option.values.map((value) => {
    const candidate: Selection = { ...selection, [axisName]: value };
    const narrowed = matchingVariants(matrix, candidate);
    const chosen = resolveVariant(matrix, candidate);
    const variantForValue =
      matrix.variants.find((v) => v.attributes?.[axisName] === value) ?? null;

    return {
      value,
      // Available means: at least one purchasable variant carries this value
      // together with the *other* selected axes. Sold out still counts as
      // present-but-disabled, which is more useful than hiding it entirely.
      available: narrowed.length > 0,
      variant: chosen,
      variantForValue,
    };
  });
}

/**
 * Apply a selection change and repair the result.
 *
 * Selecting a Material can invalidate the currently selected Size. Rather than
 * leaving a stale combination that resolves to no variant, the dependent axes
 * are cleared in axis order until the selection is internally consistent.
 */
export function applySelection(
  matrix: Matrix,
  selection: Selection,
  axisName: string,
  value: string,
): Selection {
  const next: Selection = { ...selection, [axisName]: value };

  for (const other of matrix.axes) {
    if (other === axisName) continue;
    const current = next[other];
    if (!current) continue;
    if (matchingVariants(matrix, next).length > 0) continue;
    // This axis's current value has no variant alongside the new selection.
    delete next[other];
  }
  return next;
}

/**
 * The initial selection: the API's default variant, or the first available one.
 *
 * Preferring `is_default` matters because the price shown on load should be the
 * price a shopper gets by pressing Add to Cart without touching anything.
 */
export function initialSelection(matrix: Matrix): Selection {
  const preferred = matrix.variants.find((v) => v.is_default) ?? matrix.variants[0];
  if (!preferred) return {};
  return { ...(preferred.options ?? preferred.attributes) };
}

/** The variant to add to cart, or null when the selection is incomplete. */
export function purchasableVariant(
  matrix: Matrix,
  selection: Selection,
): Variant | null {
  if (matrix.axes.length === 0) {
    // A product with no options: exactly one variant, or nothing to buy.
    return matrix.variants[0] ?? null;
  }
  if (matrix.axes.some((axis) => !selection[axis])) return null;
  const variant = resolveVariant(matrix, selection);
  if (!variant) return null;
  return variant.in_stock ? variant : null;
}

/** A human label for a selection, e.g. "3MM ACP / 18x24". */
export function selectionLabel(
  matrix: Matrix,
  selection: Selection,
): string {
  return matrix.axes
    .map((axis) => selection[axis])
    .filter(Boolean)
    .join(" / ");
}
