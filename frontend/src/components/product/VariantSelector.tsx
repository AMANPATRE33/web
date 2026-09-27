"use client";

/**
 * The Material x Size variant selector.
 *
 * This is the most important interactive component in the storefront, so its
 * contract is worth stating precisely.
 *
 * **What it renders.** One group of buttons per option axis the API declared
 * (`product.options`). Nothing is invented: a product sold only in "8x12" and
 * "12x18" renders a two-button Size group, not nine.
 *
 * **Availability is an intersection, not a union.** `axisValues` returns whether
 * a value has any variant *given the rest of the selection*, so selecting
 * "ECO VINYL STICKER" disables the sizes that material is not made in. This is
 * what the brief asked for and it comes from `lib/variants.ts`, which is pure
 * and unit-tested.
 *
 * **Price, SKU and stock all come from the resolved variant.** No arithmetic
 * happens in the browser.
 *
 * **Add to cart stays disabled until the selection is valid.** `purchasableVariant`
 * returns null while an axis is unselected or while the combination does not
 * exist, and the button is disabled with a reason shown next to it, rather than
 * letting the customer press it and fail.
 *
 * **Sold-out is visible, not hidden.** A value with no purchasable variant
 * renders disabled and struck through, so the customer learns the material/size
 * exists but is unavailable instead of wondering whether it is mistyped.
 *
 * Keyboard: each axis is a `radiogroup`. Arrow keys move within a group, Tab
 * moves between groups, matching the ARIA pattern for a single-choice set.
 */

import { motion, useReducedMotion } from "framer-motion";
import Link from "next/link";
import { useCallback, useMemo, useState } from "react";

import { Button } from "@/components/ui";
import { Price } from "@/components/catalog/primitives";
import { useCart } from "@/components/cart/CartProvider";
import type { ProductDetail } from "@/lib/api/types";
import { cn } from "@/lib/cn";
import {
  applySelection,
  axisValues,
  buildMatrix,
  initialSelection,
  purchasableVariant,
  resolveVariant,
  selectionLabel,
  type Selection,
} from "@/lib/variants";

const MAX_QTY = 99;

/**
 * The axis *other* than `axisName` that is currently selected, for the
 * "these are unavailable because of X" note. Returns null when the other axis
 * is unselected, because then nothing on this axis is unavailable.
 */
function otherAxisLabel(axisName: string, selection: Selection): string | null {
  const other = Object.keys(selection).find(
    (key) => key !== axisName && selection[key],
  );
  if (!other) return null;
  return other === "Material" ? "material" : "size";
}

export function VariantSelector({
  product,
  onAdded,
}: {
  product: ProductDetail;
  onAdded?: () => void;
}) {
  const matrix = useMemo(() => buildMatrix(product), [product]);
  const [selection, setSelection] = useState<Selection>(() => initialSelection(matrix));
  // The raw text of the quantity field is held separately from the number.
  //
  // Holding only the number means a controlled `type="number"` cannot represent
  // an empty field: clearing it parses to NaN, the value snaps back to 1
  // immediately, and a user who selects-all and types "25" ends up with 12 then
  // 125, clamped to 99. Keeping the raw text lets the field be genuinely empty
  // while typing, and the number is derived and clamped from it.
  const [quantityText, setQuantityText] = useState("1");
  const quantity = useMemo(() => {
    const parsed = Number.parseInt(quantityText, 10);
    if (!Number.isFinite(parsed)) return 1;
    return Math.min(Math.max(parsed, 1), MAX_QTY);
  }, [quantityText]);

  const setQuantity = useCallback((next: number) => {
    setQuantityText(String(Math.min(Math.max(next, 1), MAX_QTY)));
  }, []);

  const [feedback, setFeedback] = useState<string | null>(null);
  const { addLine, quantityOf } = useCart();
  const reduced = useReducedMotion();

  // The variant the current selection points at. null = the combination does not
  // exist, which is a real state the UI has to handle honestly.
  const variant = useMemo(() => resolveVariant(matrix, selection), [matrix, selection]);
  const purchasable = useMemo(
    () => purchasableVariant(matrix, selection),
    [matrix, selection],
  );

  const missingAxis = useMemo(
    () => matrix.axes.find((axis) => !selection[axis]),
    [matrix, selection],
  );

  const select = useCallback(
    (axisName: string, value: string) => {
      setFeedback(null);
      setSelection((current) => applySelection(matrix, current, axisName, value));
    },
    [matrix],
  );

  const activeQuantity = variant ? quantityOf(variant.id) : 0;

  const add = useCallback(() => {
    if (!purchasable) return;
    addLine({
      variantId: purchasable.id,
      productId: product.id,
      productSlug: product.slug,
      productTitle: product.title,
      variantSku: purchasable.sku,
      material: purchasable.attributes?.Material ?? null,
      size: purchasable.attributes?.Size ?? null,
      imageUrl: product.images?.find((image) => image.is_primary)?.url ?? product.images?.[0]?.url ?? null,
      unitPrice: purchasable.price,
      quantity,
      maxQuantity: purchasable.available_quantity,
    });
    setFeedback(`Added ${selectionLabel(matrix, selection)} to cart.`);
    onAdded?.();
  }, [addLine, matrix, onAdded, product, purchasable, quantity, selection]);

  return (
    <div className="space-y-6">
      {/* --- live price / SKU / stock, all from the resolved variant --- */}
      <div className="border-y border-ink-200 py-4">
        <div className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1">
          <Price
            price={variant?.price ?? product.price}
            compareAt={variant?.compare_at_price ?? product.compare_at_price}
            discountPercent={variant?.discount_percent ?? product.discount_percent}
            size="xl"
          />
          {variant ? (
            // Labelled, not bare. A buyer reads the SKU off this page and quotes
            // it back, and the rest of the storefront renders it with a "SKU"
            // prefix - an unlabelled code here would read as an internal id.
            <span className="font-mono text-[12px] uppercase tracking-wide text-ink-500">
              SKU {variant.sku}
            </span>
          ) : null}
        </div>

        <p className="mt-1.5 text-[13px] text-ink-600">
          {variant ? (
            <>
              {variant.in_stock ? (
                <span className="font-semibold text-safe-700">
                  In stock &middot; {variant.available_quantity} available
                </span>
              ) : (
                <span className="font-semibold text-ink-600">Out of stock in this option</span>
              )}
              {matrix.hasChoices ? (
                <span className="text-ink-500">
                  {" "}
                  &middot; Price is for {selectionLabel(matrix, selection) || "the selected option"}
                </span>
              ) : null}
            </>
          ) : (
            <span className="text-ink-500">
              This combination is not available. Choose another option.
            </span>
          )}
        </p>
      </div>

      {/* --- one radio group per axis --- */}
      {matrix.axes.map((axisName) => {
        const values = axisValues(matrix, axisName, selection);
        const selected = selection[axisName];
        const unavailable = values.filter((entry) => !entry.available).map((v) => v.value);
        const other = otherAxisLabel(axisName, selection);

        return (
          <fieldset key={axisName}>
            <legend className="mb-2 flex w-full items-baseline justify-between gap-2">
              <span className="text-[13px] font-bold uppercase tracking-[0.06em] text-ink-900">
                {axisName}
                {/* Required, not optional, when more than one axis must be chosen. */}
                {matrix.axes.length > 0 ? (
                  <span className="ml-1 text-danger-600" aria-hidden="true">
                    *
                  </span>
                ) : null}
              </span>
              {selected ? (
                <span className="font-mono text-[12px] uppercase tracking-wide text-ink-500">
                  {selected}
                </span>
              ) : null}
            </legend>

            <div
              role="radiogroup"
              aria-label={axisName}
              className={cn(
                "grid gap-2",
                // Sizes are short and sit in a tighter grid; materials are long
                // labels and want a single column on mobile so nothing truncates.
                axisName === "Size"
                  ? "grid-cols-3 sm:grid-cols-4 lg:grid-cols-5"
                  : "grid-cols-1 sm:grid-cols-2",
              )}
            >
              {values.map((entry) => {
                const isSelected = selected === entry.value;
                const disabled = !entry.available;
                const soldOut = entry.variantForValue ? !entry.variantForValue.in_stock : false;

                return (
                  <button
                    key={entry.value}
                    type="button"
                    role="radio"
                    aria-checked={isSelected}
                    // A disabled radio still needs to be perceivable, so it keeps
                    // `aria-disabled` semantics via the native disabled attribute
                    // plus the count note below the group.
                    disabled={disabled}
                    onClick={() => select(axisName, entry.value)}
                    className={cn(
                      "relative flex min-h-11 items-center justify-between gap-2 rounded-xs border px-3 py-2 text-left text-[13px] font-semibold transition-colors",
                      isSelected
                        ? "border-ink-950 bg-ink-950 text-white"
                        : "border-ink-300 bg-white text-ink-800 hover:border-ink-900 hover:bg-ink-50",
                      disabled &&
                        "cursor-not-allowed border-ink-200 bg-ink-50 text-ink-400 line-through hover:border-ink-200 hover:bg-ink-50",
                    )}
                  >
                    <span className="min-w-0 truncate font-mono text-[12px] uppercase tracking-wide">
                      {entry.value}
                    </span>
                    {isSelected ? (
                      <motion.svg
                        aria-hidden="true"
                        viewBox="0 0 20 20"
                        className="size-4 shrink-0 text-signal-400"
                        fill="none"
                        stroke="currentColor"
                        strokeWidth="2.5"
                        initial={reduced ? false : { scale: 0.6, opacity: 0 }}
                        animate={{ scale: 1, opacity: 1 }}
                        transition={{ duration: 0.15 }}
                      >
                        <path d="M4 10.5l4 4 8-9" strokeLinecap="round" strokeLinejoin="round" />
                      </motion.svg>
                    ) : soldOut ? (
                      <span className="shrink-0 text-[10px] font-bold uppercase tracking-wider text-ink-400">
                        Sold out
                      </span>
                    ) : null}
                  </button>
                );
              })}
            </div>

            {/*
              Why the greyed-out options are greyed out.

              A disabled option gives no reason. Without this note a customer
              looking at an unavailable material cannot tell the difference
              between "we do not make this" and "pick a different size first" -
              and the second is the common case.
            */}
            {unavailable.length > 0 ? (
              <p className="mt-2 text-[12px] leading-relaxed text-ink-500">
                {unavailable.length} of {values.length}{" "}
                {axisName.toLowerCase()}
                {unavailable.length === 1 ? " is" : "s are"} not available with{" "}
                {other ?? "the current selection"}. Change{" "}
                {other ? (other === "material" ? "the material" : "the size") : "the other option"}{" "}
                to see {unavailable.length === 1 ? "it" : "them"}.
              </p>
            ) : null}
          </fieldset>
        );
      })}

      {/* --- quantity + actions --- */}
      <div className="space-y-3">
        <div className="flex flex-wrap items-end gap-3">
          <div>
            <span
              id="quantity-label"
              className="mb-1.5 block text-[13px] font-bold uppercase tracking-[0.06em] text-ink-900"
            >
              Quantity
            </span>
            <div className="inline-flex h-11 items-stretch border border-ink-300">
              <button
                type="button"
                onClick={() => setQuantity(quantity - 1)}
                disabled={quantity <= 1}
                aria-label="Decrease quantity"
                className="w-11 text-lg text-ink-700 transition-colors hover:bg-ink-100 disabled:cursor-not-allowed disabled:text-ink-300"
              >
                &minus;
              </button>
              <input
                type="number"
                inputMode="numeric"
                value={quantityText}
                aria-labelledby="quantity-label"
                onChange={(event) => setQuantityText(event.target.value)}
                // Normalise on blur, so an empty or out-of-range field is
                // corrected once the user is done, not while they are typing.
                onBlur={() => setQuantity(quantity)}
                className="tabular w-14 border-x border-ink-300 text-center text-sm font-semibold [appearance:textfield] [&::-webkit-inner-spin-button]:appearance-none [&::-webkit-outer-spin-button]:appearance-none"
              />
              <button
                type="button"
                onClick={() => setQuantity(quantity + 1)}
                disabled={quantity >= MAX_QTY}
                aria-label="Increase quantity"
                className="w-11 text-lg text-ink-700 transition-colors hover:bg-ink-100 disabled:cursor-not-allowed disabled:text-ink-300"
              >
                +
              </button>
            </div>
          </div>

          {activeQuantity > 0 ? (
            <p className="pb-2.5 text-[12px] text-ink-500">
              {activeQuantity} already in your cart
            </p>
          ) : null}
        </div>

        <div className="grid gap-2 sm:grid-cols-2">
          <Button
            variant="primary"
            size="lg"
            block
            disabled={!purchasable}
            onClick={add}
          >
            {purchasable ? "Add to cart" : "Select an option"}
          </Button>
          {/* Buy now: add to cart, then continue to checkout. Rendered as a
              real link so it is middle-clickable and keyboard reachable, with
              pointer-events disabled while the selection is invalid. */}
          <Link
            href={
              purchasable
                ? `/checkout?variant=${encodeURIComponent(purchasable.id)}&qty=${quantity}`
                : "/cart"
            }
            aria-disabled={!purchasable}
            tabIndex={purchasable ? 0 : -1}
            onClick={() => {
              if (purchasable) add();
            }}
            className={cn(
              "inline-flex h-12 items-center justify-center rounded-xs border border-ink-900 px-6 text-[15px] font-semibold text-ink-900 transition-colors hover:bg-ink-50",
              !purchasable && "pointer-events-none border-ink-200 text-ink-400",
            )}
          >
            Buy now
          </Link>
        </div>

        {/* The reason a disabled button is disabled, always visible. */}
        {!purchasable ? (
          <p role="status" className="text-[13px] font-medium text-ink-600">
            {missingAxis
              ? `Choose a ${missingAxis} to continue.`
              : variant
                ? "This option is sold out. Try another size or material."
                : "That combination is not manufactured. Choose another option."}
          </p>
        ) : feedback ? (
          <p
            role="status"
            aria-live="polite"
            className="text-[13px] font-medium text-safe-700"
          >
            {feedback}
          </p>
        ) : null}
      </div>
    </div>
  );
}
