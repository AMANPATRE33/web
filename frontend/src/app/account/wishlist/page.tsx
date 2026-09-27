import type { Metadata } from "next";

import { AccountShell } from "@/components/account/AccountShell";
import { WishlistView } from "@/components/wishlist/WishlistView";

export const metadata: Metadata = {
  title: "Your wishlist",
  robots: { index: false, follow: false },
};

export default function WishlistPage() {
  return (
    <AccountShell
      title="Wishlist"
      description="Products you have saved. Wishlists are stored on this device and are not tied to an account yet."
    >
      <WishlistView />
    </AccountShell>
  );
}
