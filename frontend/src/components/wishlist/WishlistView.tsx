"use client";

/**
 * Wishlist page.
 *
 * Reads the same store the heart buttons write to, resolves the saved product
 * ids against the real catalogue API, and drops any id that no longer
 * resolves. That reconciliation is the point: a wishlist that quietly lists
 * deleted products is worse than one that forgets them.
 *
 * The empty case is *derived* from `ids` rather than assigned inside the effect,
 * so there is no setState-in-effect and no flash of skeletons for an empty list.
 */

import { Heart } from "lucide-react";
import Link from "next/link";
import { useEffect, useState } from "react";

import { ProductCard, ProductCardSkeleton } from "@/components/catalog/ProductCard";
import { useWishlist } from "@/components/wishlist/WishlistProvider";
import { Button, EmptyState } from "@/components/ui";
import { listProducts } from "@/lib/api/catalog";
import type { ProductCard as ProductCardData } from "@/lib/api/types";

interface Resolved {
  /** The id set this result was computed from, so a change invalidates it. */
  from: string;
  products: ProductCardData[];
  /** Set when the lookup itself failed, as opposed to finding nothing. */
  failed: boolean;
}

export function WishlistView() {
  const { ids } = useWishlist();
  const [resolved, setResolved] = useState<Resolved | null>(null);

  // `key` is the value-identity of `ids`. Depending on the array itself would
  // re-run the effect on every render, since the store hands back a new array.
  const key = ids.join("|");

  useEffect(() => {
    if (ids.length === 0) return;

    let cancelled = false;

    // The wishlist stores ids, and the list endpoint filters by slug, so a
    // faithful per-id lookup is a server concern. Until the wishlist API lands,
    // sweep the catalogue once and match. A wishlist longer than one page will
    // under-report, which the empty state explains rather than hides.
    //
    // All state transitions are in the promise callbacks, never in the effect
    // body: a synchronous setState here would cascade a render on every store
    // write.
    listProducts({ per_page: 100, sort: "newest" })
      .then((page) => {
        if (cancelled) return;
        const byId = new Map(page.items.map((item) => [item.id, item]));
        setResolved({
          from: key,
          products: ids
            .map((id) => byId.get(id))
            .filter((item): item is ProductCardData => Boolean(item)),
          failed: false,
        });
      })
      .catch(() => {
        if (!cancelled) setResolved({ from: key, products: [], failed: true });
      });

    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key]);

  if (ids.length === 0) {
    return (
      <EmptyState
        icon={<Heart aria-hidden="true" className="size-10" />}
        title="Your wishlist is empty"
        description="Tap the heart on any product to save it here. Useful when you are comparing materials for a site and are not ready to order yet."
        action={
          <Button variant="primary" asChild>
            <Link href="/shop">Browse products</Link>
          </Button>
        }
      />
    );
  }

  if (resolved !== null && resolved.from === key && resolved.failed) {
    return (
      <EmptyState
        title="We couldn't load your wishlist"
        description="The catalogue did not respond. Your saved items are safe on this device - please try again."
        action={
          <Button variant="outline" onClick={() => window.location.reload()}>
            Try again
          </Button>
        }
      />
    );
  }

  if (resolved === null || resolved.from !== key) {
    return (
      <div className="grid grid-cols-2 gap-3 sm:gap-4 md:grid-cols-3" aria-busy="true">
        {[0, 1, 2].map((index) => (
          <ProductCardSkeleton key={index} />
        ))}
      </div>
    );
  }

  const missing = ids.length - resolved.products.length;

  return (
    <>
      {missing > 0 ? (
        <p className="mb-5 text-[13px] text-ink-500">
          {missing} saved product{missing === 1 ? "" : "s"} could not be found in the catalogue
          and {missing === 1 ? "is" : "are"} not shown.
        </p>
      ) : null}
      {resolved.products.length === 0 ? (
        <EmptyState
          title="None of your saved products are available"
          description="They may have been discontinued. Browse the catalogue to find a replacement."
          action={
            <Button variant="primary" asChild>
              <Link href="/shop">Browse products</Link>
            </Button>
          }
        />
      ) : (
        <div className="grid grid-cols-2 gap-3 sm:gap-4 md:grid-cols-3">
          {resolved.products.map((product) => (
            <ProductCard key={product.id} product={product} />
          ))}
        </div>
      )}
    </>
  );
}
