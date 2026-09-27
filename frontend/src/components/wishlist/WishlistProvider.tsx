"use client";

/**
 * Wishlist.
 *
 * The wishlist has no API yet (a later phase), so this is a `localStorage`
 * store. When the endpoints land, only the provider changes: the heart button
 * and the wishlist page both read `useWishlist()` and never touch storage.
 */

import { createContext, useContext, useMemo, type ReactNode } from "react";
import { Heart } from "lucide-react";

import { createLocalStore, useLocalStore } from "@/lib/localStore";

const EMPTY: string[] = [];

const wishlistStore = createLocalStore<string[]>({
  key: "spp.wishlist.v1",
  eventName: "spp:wishlist-change",
  empty: EMPTY,
  parse: (raw) => (Array.isArray(raw) ? raw.filter((v): v is string => typeof v === "string") : EMPTY),
});

interface WishlistValue {
  ids: string[];
  ready: boolean;
  has: (productId: string) => boolean;
  toggle: (productId: string) => void;
  remove: (productId: string) => void;
  clear: () => void;
}

const WishlistContext = createContext<WishlistValue | null>(null);

export function WishlistProvider({ children }: { children: ReactNode }) {
  const ids = useLocalStore(wishlistStore);

  const value = useMemo<WishlistValue>(
    () => ({
      ids,
      ready: true,
      has: (productId) => ids.includes(productId),
      toggle: (productId) =>
        wishlistStore.write(
          ids.includes(productId) ? ids.filter((v) => v !== productId) : [...ids, productId],
        ),
      remove: (productId) => wishlistStore.write(ids.filter((v) => v !== productId)),
      clear: () => wishlistStore.write(EMPTY),
    }),
    [ids],
  );

  return <WishlistContext.Provider value={value}>{children}</WishlistContext.Provider>;
}

export function useWishlist(): WishlistValue {
  const context = useContext(WishlistContext);
  if (!context) throw new Error("useWishlist must be used inside <WishlistProvider>");
  return context;
}

export function WishlistButton({
  productId,
  productTitle,
  className,
  size = "md",
}: {
  productId: string;
  productTitle: string;
  className?: string;
  size?: "sm" | "md";
}) {
  const { has, toggle } = useWishlist();
  const active = has(productId);

  return (
    <button
      type="button"
      onClick={(event) => {
        // The whole card is a link; without this, tapping the heart navigates.
        event.preventDefault();
        event.stopPropagation();
        toggle(productId);
      }}
      aria-pressed={active}
      aria-label={
        active ? `Remove ${productTitle} from wishlist` : `Add ${productTitle} to wishlist`
      }
      className={
        className ??
        `inline-flex items-center justify-center rounded-xs border border-ink-200 bg-white/95 text-ink-500 shadow-sm backdrop-blur transition-colors hover:border-ink-400 hover:text-danger-600 ${
          size === "sm" ? "size-8" : "size-9"
        }`
      }
    >
      <Heart
        aria-hidden="true"
        className={size === "sm" ? "size-4" : "size-[18px]"}
        fill={active ? "currentColor" : "none"}
      />
    </button>
  );
}
