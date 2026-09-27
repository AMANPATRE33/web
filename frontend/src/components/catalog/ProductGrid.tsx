import Link from "next/link";

import { ProductCard, ProductCardSkeleton } from "@/components/catalog/ProductCard";
import type { PageMeta, ProductCard as ProductCardData } from "@/lib/api/types";
import { cn } from "@/lib/cn";

/**
 * Responsive product grid.
 *
 * The column counts are the ones the brief asked for: 4 on desktop, 3 on
 * tablet, 2 on mobile. At 1024px a 4-column grid puts a ~230px card in front of
 * a safety-signage buyer, and the size/material chips on the card become
 * unreadable - so the fourth column switches on at 1280px, not 1024px.
 */
export function ProductGrid({
  products,
  priorityCount = 4,
  className,
}: {
  products: ProductCardData[];
  priorityCount?: number;
  className?: string;
}) {
  return (
    <div
      className={cn(
        "grid grid-cols-2 gap-3 sm:gap-4 md:grid-cols-3 xl:grid-cols-4",
        className,
      )}
    >
      {products.map((product, index) => (
        <ProductCard
          key={product.id}
          product={product}
          priority={index < priorityCount}
        />
      ))}
    </div>
  );
}

export function ProductGridSkeleton({
  count = 8,
  className,
}: {
  count?: number;
  className?: string;
}) {
  return (
    <div
      className={cn(
        "grid grid-cols-2 gap-3 sm:gap-4 md:grid-cols-3 xl:grid-cols-4",
        className,
      )}
      aria-hidden="true"
    >
      {Array.from({ length: count }, (_, index) => (
        <ProductCardSkeleton key={index} />
      ))}
    </div>
  );
}

/**
 * Pagination.
 *
 * Server-rendered links, not a client component with a page state: every page
 * is a real URL, so it is crawlable, shareable and works with JS disabled. The
 * "current" page is an `<span aria-current="page">`, not a link to itself.
 *
 * The window is seven slots wide, ellipsised, so the control stays a single
 * row on a 390px screen instead of wrapping into three.
 */
export function Pagination({
  meta,
  buildHref,
  className,
}: {
  meta: PageMeta;
  buildHref: (page: number) => string;
  className?: string;
}) {
  if (meta.total_pages <= 1) return null;

  const current = meta.page;
  const last = meta.total_pages;
  const slots: Array<number | "gap"> = [];

  if (last <= 7) {
    for (let page = 1; page <= last; page += 1) slots.push(page);
  } else if (current <= 4) {
    slots.push(1, 2, 3, 4, 5, "gap", last);
  } else if (current >= last - 3) {
    slots.push(1, "gap", last - 4, last - 3, last - 2, last - 1, last);
  } else {
    slots.push(1, "gap", current - 1, current, current + 1, "gap", last);
  }

  const base =
    "inline-flex h-9 min-w-9 items-center justify-center rounded-xs border px-2 text-[13px] font-semibold transition-colors";

  return (
    <nav
      aria-label="Pagination"
      className={cn("mt-10 flex items-center justify-center gap-1.5", className)}
    >
      {current > 1 ? (
        <Link
          href={buildHref(current - 1)}
          rel="prev"
          className={cn(base, "border-ink-300 bg-white text-ink-800 hover:border-ink-900")}
        >
          <span aria-hidden="true">‹</span>
          <span className="ml-1 hidden sm:inline">Previous</span>
          <span className="sr-only">Previous page</span>
        </Link>
      ) : (
        <span className={cn(base, "border-ink-200 bg-ink-50 text-ink-300")} aria-hidden="true">
          <span className="hidden sm:inline">Previous</span>‹
        </span>
      )}

      {slots.map((slot, index) =>
        slot === "gap" ? (
          <span
            key={`gap-${index}`}
            aria-hidden="true"
            className="px-1 text-ink-400"
          >
            &hellip;
          </span>
        ) : slot === current ? (
          <span
            key={slot}
            aria-current="page"
            className={cn(base, "border-ink-950 bg-ink-950 text-white")}
          >
            {slot}
            <span className="sr-only">, current page</span>
          </span>
        ) : (
          <Link
            key={slot}
            href={buildHref(slot)}
            className={cn(base, "border-ink-300 bg-white text-ink-800 hover:border-ink-900")}
          >
            {slot}
          </Link>
        ),
      )}

      {current < last ? (
        <Link
          href={buildHref(current + 1)}
          rel="next"
          className={cn(base, "border-ink-300 bg-white text-ink-800 hover:border-ink-900")}
        >
          <span className="mr-1 hidden sm:inline">Next</span>
          <span aria-hidden="true">›</span>
          <span className="sr-only">Next page</span>
        </Link>
      ) : (
        <span className={cn(base, "border-ink-200 bg-ink-50 text-ink-300")} aria-hidden="true">
          <span className="hidden sm:inline">Next</span>›
        </span>
      )}
    </nav>
  );
}

/** "X products" / "1 product", with the range when paginating. */
export function ResultCount({
  total,
  page,
  perPage,
  noun = "product",
  className,
}: {
  total: number;
  page: number;
  perPage: number;
  noun?: string;
  className?: string;
}) {
  if (total === 0) return null;
  const from = (page - 1) * perPage + 1;
  const to = Math.min(page * perPage, total);

  return (
    <p className={cn("tabular text-[13px] text-ink-600", className)}>
      {total === 1 ? (
        <>
          <span className="font-semibold text-ink-950">1</span> {noun}
        </>
      ) : (
        <>
          <span className="font-semibold text-ink-950">{total}</span> {noun}s
          {total > perPage ? (
            <span className="text-ink-400">
              {" "}
              ({from}&ndash;{to})
            </span>
          ) : null}
        </>
      )}
    </p>
  );
}
