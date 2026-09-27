"use client";

/**
 * Cart state.
 *
 * ## Why this is local, and what that means
 *
 * The server-authoritative cart API is the next build phase. Until it exists,
 * this store holds lines in `localStorage` so the storefront is usable and the
 * variant identity rules can be exercised end to end.
 *
 * What this store does **not** do, deliberately:
 *
 *   - it never decides a price. Every amount shown came from the server when
 *     the product was loaded, and each line stores that `Money` object;
 *   - it never merges lines. Identity is `variant_id`, so 3MM ACP 18x24 and
 *     5MM FOAMSHEET 18x24 are two lines, not one with a doubled quantity;
 *   - it never claims the total is authoritative. `totals()` is explicitly
 *     labelled display-only.
 *
 * When the cart API lands, `CartProvider` becomes a client of
 * `GET/POST/PATCH/DELETE /api/v1/cart` and the components do not change,
 * because they already treat the server as the source of price.
 */

import {
  createContext,
  useCallback,
  useContext,
  useMemo,
  type ReactNode,
} from "react";

import type { Money } from "@/lib/api/types";
import { createLocalStore, useLocalStore } from "@/lib/localStore";

const MAX_PER_LINE = 99;

export interface CartLine {
  /** Server identity. The unique key for a line - never the product id. */
  variantId: string;
  productId: string;
  productSlug: string;
  productTitle: string;
  variantSku: string;
  material: string | null;
  size: string | null;
  imageUrl: string | null;
  /** From the server at the time this line was added. Display only. */
  unitPrice: Money;
  quantity: number;
  maxQuantity: number;
  addedAt: number;
}

export interface CartTotals {
  itemCount: number;
  subtotal: Money;
  /** Not authoritative. Shipping and tax are computed server-side at checkout. */
  isEstimate: true;
}

export interface AddLineInput {
  variantId: string;
  productId: string;
  productSlug: string;
  productTitle: string;
  variantSku: string;
  material: string | null;
  size: string | null;
  imageUrl: string | null;
  unitPrice: Money;
  quantity: number;
  maxQuantity: number;
}

const EMPTY_LINES: CartLine[] = [];

/**
 * A stored line is trusted only if it has the fields the cart genuinely
 * depends on. Anything else is dropped on read, so a hand-edited or truncated
 * storage value degrades to an empty cart rather than a render crash.
 */
function parseLine(value: unknown): CartLine | null {
  if (typeof value !== "object" || value === null) return null;
  const line = value as Partial<CartLine>;
  if (typeof line.variantId !== "string" || line.variantId.length === 0) return null;
  if (typeof line.quantity !== "number" || !Number.isFinite(line.quantity) || line.quantity <= 0) {
    return null;
  }
  const price = line.unitPrice;
  if (typeof price !== "object" || price === null || typeof price.amount !== "number") {
    return null;
  }
  if (typeof line.productSlug !== "string") return null;

  return {
    variantId: line.variantId,
    productId: line.productId ?? line.variantId,
    productSlug: line.productSlug,
    productTitle: line.productTitle ?? "Product",
    variantSku: line.variantSku ?? "",
    material: line.material ?? null,
    size: line.size ?? null,
    imageUrl: line.imageUrl ?? null,
    unitPrice: {
      amount: price.amount,
      currency: price.currency ?? "INR",
      symbol: price.symbol ?? "Rs.",
      formatted: price.formatted ?? "",
    },
    quantity: Math.min(Math.trunc(line.quantity), MAX_PER_LINE),
    maxQuantity:
      typeof line.maxQuantity === "number" && line.maxQuantity > 0
        ? line.maxQuantity
        : MAX_PER_LINE,
    addedAt: typeof line.addedAt === "number" ? line.addedAt : 0,
  };
}

const cartStore = createLocalStore<CartLine[]>({
  key: "spp.cart.v1",
  eventName: "spp:cart-change",
  empty: EMPTY_LINES,
  parse: (raw) => {
    if (!Array.isArray(raw)) return EMPTY_LINES;
    const lines = raw
      .map(parseLine)
      .filter((line): line is CartLine => line !== null);
    // Last write wins on duplicate variant ids, so a corrupted store cannot
    // produce two lines for the same variant and double-count the subtotal.
    const byVariant = new Map<string, CartLine>();
    for (const line of lines) byVariant.set(line.variantId, line);
    return [...byVariant.values()];
  },
});

interface CartContextValue {
  lines: CartLine[];
  ready: boolean;
  itemCount: number;
  totals: CartTotals;
  addLine: (input: AddLineInput) => void;
  setQuantity: (variantId: string, quantity: number) => void;
  removeLine: (variantId: string) => void;
  clear: () => void;
  has: (variantId: string) => boolean;
  quantityOf: (variantId: string) => number;
}

const CartContext = createContext<CartContextValue | null>(null);

export function CartProvider({ children }: { children: ReactNode }) {
  const lines = useLocalStore(cartStore);

  const addLine = useCallback(
    (input: AddLineInput) => {
      const current = cartStore.read();
      const existing = current.find((line) => line.variantId === input.variantId);

      const next = existing
        ? current.map((line) =>
            line.variantId === input.variantId
              ? {
                  ...line,
                  quantity: Math.min(line.quantity + input.quantity, MAX_PER_LINE),
                  // Refresh the server price in case it changed since page load.
                  unitPrice: input.unitPrice,
                  maxQuantity: input.maxQuantity,
                }
              : line,
          )
        : [
            ...current,
            {
              ...input,
              quantity: Math.max(1, Math.min(input.quantity, MAX_PER_LINE)),
              addedAt: Date.now(),
            },
          ];

      cartStore.write(next);
    },
    [],
  );

  const setQuantity = useCallback((variantId: string, quantity: number) => {
    const current = cartStore.read();
    const next =
      quantity <= 0
        ? current.filter((line) => line.variantId !== variantId)
        : current.map((line) =>
            line.variantId === variantId
              ? { ...line, quantity: Math.min(quantity, MAX_PER_LINE) }
              : line,
          );
    cartStore.write(next);
  }, []);

  const removeLine = useCallback((variantId: string) => {
    cartStore.write(cartStore.read().filter((line) => line.variantId !== variantId));
  }, []);

  const clear = useCallback(() => cartStore.write(EMPTY_LINES), []);

  const value = useMemo<CartContextValue>(() => {
    const itemCount = lines.reduce((total, line) => total + line.quantity, 0);
    const subtotalAmount = lines.reduce(
      (total, line) => total + line.unitPrice.amount * line.quantity,
      0,
    );
    const symbol = lines[0]?.unitPrice.symbol ?? "Rs.";
    const currency = lines[0]?.unitPrice.currency ?? "INR";

    return {
      lines,
      // Hydration is handled by useSyncExternalStore, so there is no "not ready
      // yet" window to guard. Kept as a field so callers can stay explicit.
      ready: true,
      itemCount,
      totals: {
        itemCount,
        subtotal: {
          amount: subtotalAmount,
          currency,
          symbol,
          formatted: formatAmount(subtotalAmount, symbol),
        },
        isEstimate: true,
      },
      addLine,
      setQuantity,
      removeLine,
      clear,
      has: (variantId) => lines.some((line) => line.variantId === variantId),
      quantityOf: (variantId) =>
        lines.find((line) => line.variantId === variantId)?.quantity ?? 0,
    };
  }, [lines, addLine, setQuantity, removeLine, clear]);

  return <CartContext.Provider value={value}>{children}</CartContext.Provider>;
}

/** Local grouping for the cart subtotal. Mirrors the server formatter. */
function formatAmount(amount: number, symbol: string): string {
  const sign = amount < 0 ? "-" : "";
  const abs = Math.abs(Math.trunc(amount));
  const rupees = Math.floor(abs / 100);
  const paise = abs % 100;
  const digits = String(rupees);

  let whole = digits;
  if (digits.length > 3) {
    const head = digits.slice(0, -3);
    const tail = digits.slice(-3);
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
    ? `${sign}${symbol}${whole}.${String(paise).padStart(2, "0")}`
    : `${sign}${symbol}${whole}`;
}

export function useCart(): CartContextValue {
  const context = useContext(CartContext);
  if (!context) {
    throw new Error("useCart must be used inside <CartProvider>");
  }
  return context;
}
