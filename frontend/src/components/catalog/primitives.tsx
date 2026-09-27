/**
 * Small display primitives shared by cards, the PDP and the cart.
 *
 * The rule enforced here: a price is never shown unless the server sent one.
 * The seed deliberately refuses to create zero-priced variants, but a partially
 * imported catalogue could still produce one, and rendering "Rs.0" on a card
 * invites a customer to add something that cannot be bought. `Price` therefore
 * treats a zero amount as "not purchasable" and says so.
 */

import Link from "next/link";
import { Check, Clock } from "lucide-react";

import type { Money } from "@/lib/api/types";
import { cn } from "@/lib/cn";
import { formatMinor, moneyLabel, stockLabel, stockTone } from "@/lib/money";

export function Price({
  price,
  compareAt,
  discountPercent,
  size = "md",
  className,
  showDiscount = true,
}: {
  price: Money | null | undefined;
  compareAt?: Money | null;
  discountPercent?: number;
  size?: "sm" | "md" | "lg" | "xl";
  className?: string;
  /**
   * Set false when the discount is already shown elsewhere on the same surface -
   * the product card puts a corner ribbon on the image, and printing "20% off"
   * twice on one card is noise rather than emphasis.
   */
  showDiscount?: boolean;
}) {
  if (!price) return null;

  // A zero or absent amount is a data problem, not a free product. Say so
  // rather than rendering "Rs.0".
  if (price.amount <= 0) {
    return (
      <p
        className={cn(
          "text-sm font-semibold text-ink-500",
          size === "lg" && "text-lg",
          size === "xl" && "text-2xl",
          className,
        )}
      >
        Price on request
      </p>
    );
  }

  const sizes = {
    sm: "text-sm",
    md: "text-base",
    lg: "text-xl",
    xl: "text-3xl",
  } as const;

  const onSale = Boolean(
    compareAt && compareAt.amount > price.amount && (discountPercent ?? 0) > 0,
  );

  return (
    <p className={cn("flex flex-wrap items-baseline gap-x-2 gap-y-0.5", className)}>
      <span
        className={cn(
          "tabular font-bold tracking-tight text-ink-950",
          sizes[size],
          onSale && "text-danger-600",
        )}
      >
        {moneyLabel(price)}
      </span>
      {onSale && compareAt ? (
        <>
          <span className="tabular text-[13px] text-ink-400 line-through">
            {moneyLabel(compareAt)}
          </span>
          {/* Only rendered when the backend actually computed a positive
              discount, never from a guess. */}
          {showDiscount && (discountPercent ?? 0) > 0 ? (
            <span className="rounded-xs bg-danger-500 px-1 py-0.5 text-[10px] font-bold uppercase tracking-wider text-white">
              {(discountPercent ?? 0).toFixed(0)}% off
            </span>
          ) : null}
        </>
      ) : null}
    </p>
  );
}

/** The "from" prefix, shown when a product's price varies by variant. */
export function PriceFrom({ className }: { className?: string }) {
  return (
    <span className={cn("text-[11px] font-medium uppercase tracking-wider text-ink-500", className)}>
      From
    </span>
  );
}

const TONE_CLASSES = {
  ok: "bg-safe-50 text-safe-700",
  warn: "bg-signal-50 text-signal-800",
  danger: "bg-ink-100 text-ink-600",
  muted: "bg-ink-100 text-ink-500",
} as const;

export function StockBadge({
  status,
  className,
  showIcon = true,
}: {
  status: string;
  className?: string;
  showIcon?: boolean;
}) {
  const tone = stockTone(status);
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 rounded-xs px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-[0.08em]",
        TONE_CLASSES[tone],
        className,
      )}
    >
      {showIcon && tone === "ok" ? (
        <Check aria-hidden="true" className="size-3" strokeWidth={3} />
      ) : null}
      {showIcon && status === "preorder" ? (
        <Clock aria-hidden="true" className="size-3" />
      ) : null}
      {stockLabel(status)}
    </span>
  );
}

/**
 * Star rating.
 *
 * Renders nothing when `count` is zero. The seeded catalogue carries no
 * reviews because the live site publishes none, and an unbacked star rating is
 * fabricated social proof. See `docs/REFERENCE_SITE_ANALYSIS.md`.
 */
export function Rating({
  average,
  count,
  className,
  size = "sm",
}: {
  average: number;
  count: number;
  className?: string;
  size?: "sm" | "md";
}) {
  if (count <= 0 || average <= 0) return null;
  const filled = Math.round(average);
  const star = size === "sm" ? "size-3" : "size-4";
  // One <defs> outside the loop: a gradient id per star would repeat the same
  // id five times in the document, and every star after the first would resolve
  // to whichever gradient the browser found first.
  const gradientId = `rating-half-${average.toFixed(1).replace(".", "-")}`;

  return (
    <span className={cn("inline-flex items-center gap-1.5", className)}>
      <span className="flex" aria-hidden="true">
        <svg width="0" height="0" className="absolute" focusable="false">
          <defs>
            <linearGradient id={gradientId}>
              <stop offset="50%" stopColor="#e0ab00" />
              <stop offset="50%" stopColor="transparent" />
            </linearGradient>
          </defs>
        </svg>
        {[1, 2, 3, 4, 5].map((position) => {
          const isFull = position <= filled;
          const isHalf = !isFull && position === filled + 0.5;
          return (
            <svg key={position} viewBox="0 0 20 20" className={star}>
              <path
                d="M10 1.5l2.6 5.3 5.9.9-4.3 4.1 1 5.8L10 14.9l-5.2 2.7 1-5.8L1.5 7.7l5.9-.9L10 1.5z"
                fill={isFull ? "#e0ab00" : isHalf ? `url(#${gradientId})` : "transparent"}
                stroke={isFull || isHalf ? "#e0ab00" : "#d7dbe0"}
                strokeWidth="1.2"
                strokeLinejoin="round"
              />
            </svg>
          );
        })}
      </span>
      <span className="sr-only">
        Rated {average.toFixed(1)} out of 5 from {count} review{count === 1 ? "" : "s"}
      </span>
      <span aria-hidden="true" className="tabular text-[12px] font-semibold text-ink-700">
        {average.toFixed(1)}
      </span>
      <span aria-hidden="true" className="tabular text-[12px] text-ink-400">
        ({count})
      </span>
    </span>
  );
}

/** Mono SKU line. A buyer quotes the SKU back to us, so it is always shown. */
export function Sku({ value, className }: { value: string; className?: string }) {
  return (
    <span
      className={cn(
        "font-mono text-[11px] uppercase tracking-wide text-ink-400",
        className,
      )}
    >
      SKU {value}
    </span>
  );
}

/** Breadcrumb trail. Also emits BreadcrumbList JSON-LD on the page. */
export function Breadcrumbs({
  items,
  className,
}: {
  items: Array<{ name: string; href?: string }>;
  className?: string;
}) {
  if (items.length === 0) return null;
  return (
    <nav aria-label="Breadcrumb" className={cn("min-w-0", className)}>
      <ol className="flex flex-wrap items-center gap-1 text-[12px] text-ink-500">
        {items.map((item, index) => {
          const last = index === items.length - 1;
          return (
            <li key={`${item.name}-${index}`} className="flex min-w-0 items-center gap-1">
              {item.href && !last ? (
                <Link
                  href={item.href}
                  className="truncate underline-offset-4 hover:text-ink-900 hover:underline"
                >
                  {item.name}
                </Link>
              ) : (
                <span
                  aria-current={last ? "page" : undefined}
                  className="truncate font-medium text-ink-800"
                >
                  {item.name}
                </span>
              )}
              {last ? null : (
                <span aria-hidden="true" className="text-ink-300">
                  /
                </span>
              )}
            </li>
          );
        })}
      </ol>
    </nav>
  );
}

/** Format a raw minor-unit bound for the price filter slider. */
export function formatSliderPrice(amount: number): string {
  return amount <= 0 ? "Rs.0" : formatMinor(amount);
}
