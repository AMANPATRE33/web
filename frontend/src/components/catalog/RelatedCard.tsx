import Link from "next/link";

import { ProductImage } from "@/components/catalog/ProductImage";
import { Price, StockBadge } from "@/components/catalog/primitives";
import { WishlistButton } from "@/components/wishlist/WishlistProvider";
import type { RelatedProduct } from "@/lib/api/types";

/**
 * Compact card for the related-products row.
 *
 * A separate component rather than reusing `ProductCard`, because the
 * `/products/{slug}/related` endpoint returns a deliberately smaller shape: no
 * SKU, no category, no tags, no stock count. Stretching `ProductCard`'s
 * required fields onto that response would mean inventing values, so this card
 * renders exactly the fields the API does return and shows nothing else.
 */
export function RelatedCard({ product }: { product: RelatedProduct }) {
  return (
    <article className="group relative flex flex-col border border-ink-200 bg-white transition-[border-color,box-shadow] hover:border-ink-400 hover:shadow-[0_2px_12px_rgba(11,13,16,0.08)] focus-within:border-ink-900">
      <div className="relative aspect-square overflow-hidden border-b border-ink-100">
        <Link
          href={`/products/${product.slug}`}
          tabIndex={-1}
          aria-hidden="true"
          className="absolute inset-0"
        >
          <ProductImage
            src={product.primary_image?.url}
            alt={product.primary_image?.alt_text ?? product.title}
            width={product.primary_image?.width ?? 800}
            height={product.primary_image?.height ?? 800}
            sizes="(min-width: 768px) 25vw, 50vw"
            className="size-full p-4 transition-transform duration-300 group-hover:scale-[1.03]"
          />
        </Link>
        <div className="absolute right-2 top-2">
          <WishlistButton productId={product.id} productTitle={product.title} size="sm" />
        </div>
      </div>

      <div className="flex flex-1 flex-col p-3">
        <h3 className="text-[13px] font-semibold leading-snug text-ink-950">
          <Link
            href={`/products/${product.slug}`}
            className="line-clamp-2 after:absolute after:inset-0 after:content-[''] hover:underline"
          >
            {product.title}
          </Link>
        </h3>
        <div className="mt-2">
          <StockBadge status={product.in_stock ? "in_stock" : "out_of_stock"} />
        </div>
        <div className="mt-auto pt-2">
          <Price
            price={product.price}
            compareAt={product.compare_at_price}
            discountPercent={product.discount_percent}
            size="sm"
          />
        </div>
      </div>
    </article>
  );
}
