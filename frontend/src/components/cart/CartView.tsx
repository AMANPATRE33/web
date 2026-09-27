"use client";

/**
 * Cart.
 *
 * Line identity is the **variant id**, not the product id. A buyer who needs
 * 3MM ACP 18x24 and 5MM FOAMSHEET 18x24 gets two lines with two SKUs and two
 * prices, which is how the business quotes them. Merging them would silently
 * deliver the wrong material.
 *
 * Every unit price shown came from the server when the line was added. The
 * subtotal is a sum of those, which is display-only; shipping, tax and the
 * payable total are computed server-side at checkout, and the panel says so
 * rather than inventing a GST figure the business has not published.
 */

import { AnimatePresence, motion, useReducedMotion } from "framer-motion";
import { Minus, Plus, ShoppingBag, Trash2 } from "lucide-react";
import Link from "next/link";

import { useCart } from "@/components/cart/CartProvider";
import { ProductImage } from "@/components/catalog/ProductImage";
import { EmptyState } from "@/components/ui";
import { cn } from "@/lib/cn";

export function CartView({ compact = false }: { compact?: boolean }) {
  const { lines, ready, itemCount, totals, setQuantity, removeLine, clear } = useCart();
  const reduced = useReducedMotion();

  if (!ready) {
    return (
      <div className="grid gap-6 lg:grid-cols-[1fr_360px]" aria-busy="true">
        <div className="space-y-3">
          {[0, 1].map((index) => (
            <div
              key={index}
              className="h-32 animate-pulse rounded-xs border border-ink-200 bg-ink-50"
            />
          ))}
        </div>
        <div className="h-64 animate-pulse rounded-xs border border-ink-200 bg-ink-50" />
      </div>
    );
  }

  if (lines.length === 0) {
    return (
      <EmptyState
        icon={<ShoppingBag aria-hidden="true" className="size-10" />}
        title="Your cart is empty"
        description="Browse the catalogue and add the safety signage you need. Every board is priced by material and size, so pick the combination that fits your site."
        action={
          <Link
            href="/shop"
            className="inline-flex h-11 items-center justify-center rounded-xs border border-ink-950 bg-signal-400 px-5 text-sm font-semibold text-ink-950 hover:bg-signal-300"
          >
            Shop all products
          </Link>
        }
      />
    );
  }

  return (
    <div className={cn("grid gap-6", !compact && "lg:grid-cols-[1fr_360px] lg:items-start")}>
      <div>
        <ul className="divide-y divide-ink-200 border-y border-ink-200">
          <AnimatePresence initial={false}>
            {lines.map((line) => (
              <motion.li
                key={line.variantId}
                layout={!reduced}
                initial={reduced ? false : { opacity: 0, height: 0 }}
                animate={{ opacity: 1, height: "auto" }}
                exit={reduced ? undefined : { opacity: 0, height: 0 }}
                transition={{ duration: 0.2, ease: [0.22, 1, 0.36, 1] }}
                className="overflow-hidden"
              >
                <div className="flex gap-3 py-4 sm:gap-4">
                  <Link
                    href={`/products/${line.productSlug}`}
                    className="shrink-0 border border-ink-200 bg-white"
                  >
                    <ProductImage
                      src={line.imageUrl}
                      alt={line.productTitle}
                      width={96}
                      height={96}
                      sizes="96px"
                      className="size-20 p-1.5 sm:size-24 sm:p-2"
                    />
                  </Link>

                  <div className="flex min-w-0 flex-1 flex-col">
                    <div className="flex items-start justify-between gap-2">
                      <div className="min-w-0">
                        <h3 className="text-[14px] font-semibold leading-snug text-ink-950">
                          <Link
                            href={`/products/${line.productSlug}`}
                            className="line-clamp-2 hover:underline"
                          >
                            {line.productTitle}
                          </Link>
                        </h3>
                        <p className="mt-1 flex flex-wrap items-center gap-x-2 gap-y-0.5 text-[12px] text-ink-600">
                          {line.material ? (
                            <span className="font-mono uppercase tracking-wide">
                              {line.material}
                            </span>
                          ) : null}
                          {line.size ? (
                            <span className="font-mono uppercase tracking-wide">
                              {line.size} in.
                            </span>
                          ) : null}
                        </p>
                        <p className="mt-0.5 font-mono text-[11px] uppercase tracking-wide text-ink-400">
                          {line.variantSku}
                        </p>
                      </div>

                      <button
                        type="button"
                        onClick={() => removeLine(line.variantId)}
                        aria-label={`Remove ${line.productTitle} ${line.material ?? ""} ${line.size ?? ""} from cart`}
                        className="shrink-0 rounded-xs p-1.5 text-ink-400 transition-colors hover:bg-danger-50 hover:text-danger-600"
                      >
                        <Trash2 aria-hidden="true" className="size-4" />
                      </button>
                    </div>

                    <div className="mt-auto flex flex-wrap items-end justify-between gap-3 pt-3">
                      <div className="inline-flex h-9 items-stretch border border-ink-300">
                        <button
                          type="button"
                          onClick={() => setQuantity(line.variantId, line.quantity - 1)}
                          aria-label={`Decrease quantity of ${line.productTitle}`}
                          className="w-9 text-ink-700 transition-colors hover:bg-ink-100"
                        >
                          <Minus aria-hidden="true" className="mx-auto size-3.5" />
                        </button>
                        <span className="tabular flex w-10 items-center justify-center border-x border-ink-300 text-sm font-semibold">
                          {line.quantity}
                        </span>
                        <button
                          type="button"
                          onClick={() => setQuantity(line.variantId, line.quantity + 1)}
                          disabled={line.quantity >= Math.min(line.maxQuantity, 99)}
                          aria-label={`Increase quantity of ${line.productTitle}`}
                          className="w-9 text-ink-700 transition-colors hover:bg-ink-100 disabled:cursor-not-allowed disabled:text-ink-300"
                        >
                          <Plus aria-hidden="true" className="mx-auto size-3.5" />
                        </button>
                      </div>

                      <div className="text-right">
                        <p className="tabular text-[15px] font-bold text-ink-950">
                          {line.unitPrice.formatted} &times; {line.quantity}
                        </p>
                        <p className="tabular text-[13px] font-semibold text-ink-700">
                          {formatLineTotal(line.unitPrice.amount * line.quantity, line.unitPrice.symbol)}
                        </p>
                      </div>
                    </div>
                  </div>
                </div>
              </motion.li>
            ))}
          </AnimatePresence>
        </ul>

        <div className="mt-4 flex flex-wrap items-center justify-between gap-3">
          <button
            type="button"
            onClick={clear}
            className="text-[13px] font-semibold text-ink-600 underline underline-offset-4 hover:text-danger-600"
          >
            Clear cart
          </button>
          <Link
            href="/shop"
            className="text-[13px] font-semibold text-ink-900 underline underline-offset-4"
          >
            Continue shopping
          </Link>
        </div>
      </div>

      {/* --- summary --- */}
      <aside
        aria-label="Order summary"
        className="border border-ink-200 bg-ink-50 p-5 lg:sticky lg:top-32"
      >
        <h2 className="text-[15px] font-bold text-ink-950">Order summary</h2>

        <dl className="mt-4 space-y-2 text-sm">
          <div className="flex justify-between">
            <dt className="text-ink-600">
              Subtotal ({itemCount} item{itemCount === 1 ? "" : "s"})
            </dt>
            <dd className="tabular font-semibold text-ink-950">
              {totals.subtotal.formatted}
            </dd>
          </div>
          <div className="flex justify-between">
            <dt className="text-ink-600">Shipping</dt>
            <dd className="text-ink-500">Calculated at checkout</dd>
          </div>
          <div className="flex justify-between">
            <dt className="text-ink-600">GST</dt>
            <dd className="text-ink-500">Calculated at checkout</dd>
          </div>
        </dl>

        <div className="mt-4 flex items-baseline justify-between border-t border-ink-300 pt-4">
          <span className="text-sm font-semibold text-ink-900">Estimated total</span>
          <span className="tabular text-xl font-bold text-ink-950">
            {totals.subtotal.formatted}
          </span>
        </div>
        <p className="mt-2 text-[12px] leading-relaxed text-ink-500">
          Excludes shipping and GST, which are applied server-side once your delivery address
          and GSTIN are confirmed. Prices shown are what the catalogue returned when each item was
          added.
        </p>

        <div className="mt-5 space-y-2">
          <Link
            href="/checkout"
            className="inline-flex h-12 w-full items-center justify-center rounded-xs border border-ink-950 bg-signal-400 px-5 text-[15px] font-semibold text-ink-950 transition-colors hover:bg-signal-300"
          >
            Proceed to checkout
          </Link>
          <Link
            href="/bulk-order"
            className="inline-flex h-11 w-full items-center justify-center rounded-xs border border-ink-900 bg-white px-5 text-sm font-semibold text-ink-900 transition-colors hover:bg-ink-50"
          >
            Need a bulk quote?
          </Link>
        </div>
      </aside>
    </div>
  );
}

function formatLineTotal(amount: number, symbol: string): string {
  const rupees = Math.floor(amount / 100);
  const paise = amount % 100;
  const digits = String(rupees);
  const tail = digits.slice(-3);
  const head = digits.slice(0, -3);
  let whole = digits;
  if (head) {
    const groups: string[] = [];
    let rest = head;
    while (rest.length > 2) {
      groups.unshift(rest.slice(-2));
      rest = rest.slice(0, -2);
    }
    groups.unshift(rest);
    whole = `${groups.join(",")},${tail}`;
  }
  return paise > 0
    ? `${symbol}${whole}.${String(paise).padStart(2, "0")}`
    : `${symbol}${whole}`;
}
