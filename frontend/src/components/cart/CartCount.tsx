"use client";

import { useCart } from "@/components/cart/CartProvider";
import { cn } from "@/lib/cn";

/**
 * Cart item count badge.
 *
 * Renders nothing at zero rather than a "0". An empty badge is a small lie
 * about whether there is anything in the cart, and it is a permanent
 * decoration on every page.
 *
 * It also reserves its own width when visible so appearing does not nudge the
 * cart icon sideways.
 */
export function CartCount({ className }: { className?: string }) {
  const { itemCount, ready } = useCart();

  if (!ready || itemCount === 0) return null;

  return (
    <span
      className={cn(
        "tabular absolute -right-0.5 -top-0.5 flex h-[18px] min-w-[18px] items-center justify-center rounded-full bg-signal-400 px-1 text-[10px] font-bold text-ink-950 ring-2 ring-white",
        className,
      )}
    >
      {itemCount > 99 ? "99+" : itemCount}
      <span className="sr-only">
        {itemCount === 1 ? "1 item" : `${itemCount} items`} in cart
      </span>
    </span>
  );
}
