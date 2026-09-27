"use client";

import Link from "next/link";

import { ProductImage } from "@/components/catalog/ProductImage";
import { Price, PriceFrom, Rating, Sku, StockBadge } from "@/components/catalog/primitives";
import { WishlistButton } from "@/components/wishlist/WishlistProvider";
import type { ProductCard as ProductCardData } from "@/lib/api/types";
import { cn } from "@/lib/cn";
import { hasRealRating } from "@/lib/money";

/**
 * The product card.
 *
 * Design rules, each of which exists for a reason:
 *
 *  - **No "Add to cart" button on the card.** A card cannot hold a valid
 *    variant selection, and 3MM ACP / 18x24 and 5MM FOAMSHEET / 18x24 are
 *    different products at different prices. A card-level quick add that guessed
 *    a variant would sell the wrong thing. The wishlist heart is the only
 *    inline action.
 *  - **Price shows "From"** whenever variants are cheaper than the headline
 *    figure, because the headline is the cheapest variant, not the price of
 *    the board a buyer usually wants.
 *  - **No Rs.0.** A zero amount renders as "Price on request" - see `Price`.
 *  - **Aspect ratio fixed** at 1:1 with `object-contain`, so a grid of mixed
 *    portrait boards and landscape boards does not reflow when images land.
 *  - **The card is visible immediately.** An earlier version faded it in with
 *    `whileInView`, which starts every card at `opacity: 0`. If the
 *    IntersectionObserver never fires - a browser without it, a
 *    server-rendered snapshot, a headless crawler - the product is invisible.
 *    Hiding sellable inventory behind an animation is not a trade worth making,
 *    so the entrance animation was removed and only the CSS hover transition
 *    remains.
 *  - The entire card is a single link target. The heart sits above it and stops
 *    propagation, so it stays independently focusable and operable.
 *  - `prefetch={false}` on the image overlay. The card contains two links to
 *    the same product - the stretched overlay and the title - so Next was
 *    prefetching the product route twice for every card on the page. The title
 *    link keeps the prefetch, since that is the one a reader actually aims at.
 */
export function ProductCard({
  product,
  priority = false,
  className,
  showSku = true,
}: {
  product: ProductCardData;
  /** Set on the first row so the LCP image is not lazy-loaded. */
  priority?: boolean;
  className?: string;
  showSku?: boolean;
}) {
  const hasRating = hasRealRating(product.rating_count);
  const soldOut = !product.in_stock;

  return (
    <article
      className={cn(
        "group relative flex min-w-0 flex-col border border-ink-200 bg-white",
        "transition-[border-color,box-shadow] duration-200",
        "hover:border-ink-400 hover:shadow-[0_2px_12px_rgba(11,13,16,0.08)]",
        "focus-within:border-ink-900",
        soldOut && "opacity-90",
        className,
      )}
    >
      <div className="relative aspect-square overflow-hidden border-b border-ink-100">
        <Link
          href={`/products/${product.slug}`}
          tabIndex={-1}
          aria-hidden="true"
          prefetch={false}
          className="absolute inset-0 z-0"
        >
          <ProductImage
            src={product.primary_image?.url}
            alt={product.primary_image?.alt_text ?? product.title}
            width={product.primary_image?.width ?? 800}
            height={product.primary_image?.height ?? 800}
            sizes="(min-width: 1280px) 22vw, (min-width: 1024px) 25vw, (min-width: 768px) 33vw, 50vw"
            priority={priority}
            className="size-full p-4 transition-transform duration-300 group-hover:scale-[1.03]"
            imageClassName="object-contain"
          />
        </Link>

        <div className="pointer-events-none absolute inset-x-2 top-2 z-10 flex items-start justify-between gap-2">
          <div className="flex flex-col items-start gap-1">
            {/* Discount badge only when the backend computed a real one. */}
            {product.is_on_sale && product.discount_percent > 0 ? (
              <span className="rounded-xs bg-danger-500 px-1.5 py-0.5 text-[10px] font-bold uppercase tracking-wider text-white">
                {product.discount_percent.toFixed(0)}% off
              </span>
            ) : null}
            {product.is_featured ? (
              <span className="rounded-xs bg-ink-950 px-1.5 py-0.5 text-[10px] font-bold uppercase tracking-wider text-white">
                Featured
              </span>
            ) : null}
            {soldOut ? (
              <span className="rounded-xs bg-ink-700 px-1.5 py-0.5 text-[10px] font-bold uppercase tracking-wider text-white">
                Sold out
              </span>
            ) : null}
          </div>
          <div className="pointer-events-auto">
            <WishlistButton productId={product.id} productTitle={product.title} size="sm" />
          </div>
        </div>

        {product.image_count > 1 ? (
          <span className="pointer-events-none absolute bottom-2 right-2 z-10 rounded-xs bg-ink-950/80 px-1.5 py-0.5 text-[10px] font-semibold text-white">
            {product.image_count} images
          </span>
        ) : null}
      </div>

      <div className="flex min-w-0 flex-1 flex-col p-3 sm:p-4">
        {/*
          `min-w-0` on both the column and the row is required for `truncate` to
          work. A flex item defaults to `min-width: auto` and so refuses to
          shrink below its content width, which lets a long category name escape
          the card and push the page sideways at 390px.
        */}
        <p className="min-w-0 truncate text-[11px] font-medium uppercase tracking-[0.06em] text-ink-500">
          <Link
            href={`/category/${product.category_slug}`}
            className="underline-offset-4 hover:text-ink-900 hover:underline"
          >
            {product.category_name}
          </Link>
        </p>

        <h3 className="mt-1.5 min-w-0 text-[14px] font-semibold leading-snug text-ink-950">
          <Link
            href={`/products/${product.slug}`}
            className="line-clamp-2 rounded-xs after:absolute after:inset-0 after:content-[''] hover:underline"
          >
            {product.title}
          </Link>
        </h3>

        {product.short_description ? (
          <p className="mt-1 line-clamp-2 text-[12px] leading-relaxed text-ink-500">
            {product.short_description}
          </p>
        ) : null}

        <div className="mt-2 flex items-center gap-2">
          <StockBadge status={product.stock_status} />
          {hasRating ? <Rating average={product.rating_average} count={product.rating_count} /> : null}
        </div>

        <div className="mt-auto min-w-0 pt-3">
          <div className="flex items-end justify-between gap-2">
            <div className="min-w-0">
              <PriceFrom className="mb-0.5 block" />
              <Price
                price={product.price}
                compareAt={product.compare_at_price}
                discountPercent={product.discount_percent}
                size="md"
                // The corner ribbon already carries the discount on this card.
                showDiscount={false}
              />
            </div>
          </div>
          {showSku ? (
            <Sku value={product.sku} className="mt-2 block truncate" />
          ) : null}
        </div>
      </div>
    </article>
  );
}

/** Skeleton matching the card's exact layout, so the grid does not jump. */
export function ProductCardSkeleton() {
  return (
    <div className="flex flex-col border border-ink-200 bg-white">
      <div className="aspect-square animate-pulse border-b border-ink-100 bg-ink-100" />
      <div className="space-y-2 p-3 sm:p-4">
        <div className="h-2.5 w-16 animate-pulse rounded-xs bg-ink-200" />
        <div className="h-4 w-full animate-pulse rounded-xs bg-ink-200" />
        <div className="h-4 w-2/3 animate-pulse rounded-xs bg-ink-200" />
        <div className="h-4 w-24 animate-pulse rounded-xs bg-ink-200" />
        <div className="h-5 w-20 animate-pulse rounded-xs bg-ink-200" />
      </div>
    </div>
  );
}
