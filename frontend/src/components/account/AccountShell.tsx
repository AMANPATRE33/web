"use client";

/**
 * Account shell.
 *
 * The authentication backend is built and verified (Supabase JWT verification,
 * role checks, CSRF for cookie sessions) but the browser sign-in screen is a
 * later phase. Until then this page states that plainly and still renders the
 * account navigation, so the routes exist, are linked, and are crawlable rather
 * than 404ing from the header.
 *
 * What it deliberately does not do is fake a signed-in session, show a fake
 * customer name, or render a fake order history. An account page with invented
 * data is worse than an honest "not signed in".
 */

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  Heart,
  LogOut,
  MapPin,
  Package,
  ShoppingBag,
  User,
} from "lucide-react";
import type { ReactNode } from "react";

import { cn } from "@/lib/cn";

const NAV = [
  { href: "/account", label: "Overview", icon: User, exact: true },
  { href: "/account/orders", label: "Orders", icon: ShoppingBag },
  { href: "/account/wishlist", label: "Wishlist", icon: Heart },
  { href: "/account/addresses", label: "Addresses", icon: MapPin },
  { href: "/account/profile", label: "Profile", icon: User },
];

export function AccountShell({
  title,
  description,
  children,
}: {
  title: string;
  description?: string;
  children: ReactNode;
}) {
  const pathname = usePathname();

  return (
    <div className="container-page py-10 sm:py-14">
      <nav aria-label="Breadcrumb" className="mb-6">
        <ol className="flex items-center gap-1 text-[12px] text-ink-500">
          <li>
            <Link href="/" className="hover:text-ink-900 hover:underline">
              Home
            </Link>
          </li>
          <li aria-hidden="true" className="text-ink-300">
            /
          </li>
          <li aria-current="page" className="font-medium text-ink-800">
            Account
          </li>
        </ol>
      </nav>

      <div className="grid gap-8 lg:grid-cols-[240px_1fr] lg:items-start">
        <aside>
          <h1 className="text-xl sm:text-2xl">{title}</h1>
          {description ? (
            <p className="mt-2 text-[13px] leading-relaxed text-ink-600">{description}</p>
          ) : null}
          <nav aria-label="Account" className="mt-6">
            <ul className="space-y-0.5">
              {NAV.map((item) => {
                const active = item.exact
                  ? pathname === item.href
                  : pathname.startsWith(item.href);
                return (
                  <li key={item.href}>
                    <Link
                      href={item.href}
                      aria-current={active ? "page" : undefined}
                      className={cn(
                        "flex items-center gap-2.5 rounded-xs px-3 py-2 text-[13px] font-medium transition-colors",
                        active
                          ? "bg-ink-950 text-white"
                          : "text-ink-700 hover:bg-ink-100 hover:text-ink-950",
                      )}
                    >
                      <item.icon aria-hidden="true" className="size-4 shrink-0" />
                      {item.label}
                    </Link>
                  </li>
                );
              })}
            </ul>
          </nav>
        </aside>

        <div className="min-w-0">{children}</div>
      </div>
    </div>
  );
}

/**
 * The signed-out state, shown on every account route for now.
 *
 * Kept as one component so the wording, the reason and the next step are
 * identical everywhere rather than drifting page to page.
 */
export function SignInRequired({ what }: { what: string }) {
  return (
    <div className="border border-dashed border-ink-300 bg-ink-50 p-6 sm:p-8">
      <p className="flex items-center gap-2.5 text-[15px] font-semibold text-ink-950">
        <LogOut aria-hidden="true" className="size-4 text-ink-400" />
        Sign in to see {what}
      </p>
      <p className="mt-3 max-w-lg text-[14px] leading-relaxed text-ink-600">
        Account sign-in is not enabled on this storefront yet. The authentication layer behind it
        is built and verified, but there is no sign-in screen, so there is nothing for you to log
        in to.
      </p>
      <p className="mt-3 max-w-lg text-[14px] leading-relaxed text-ink-600">
        You do not need an account to order. Add boards to your cart and check out as a guest.
        For a site-wide order, the{" "}
        <Link href="/bulk-order" className="font-semibold underline underline-offset-4">
          bulk quote form
        </Link>{" "}
        is faster than registering.
      </p>
      <div className="mt-5 flex flex-wrap gap-2">
        <Link
          href="/shop"
          className="inline-flex h-11 items-center justify-center rounded-xs border border-ink-950 bg-signal-400 px-5 text-sm font-semibold text-ink-950 hover:bg-signal-300"
        >
          Continue shopping
        </Link>
        <Link
          href="/cart"
          className="inline-flex h-11 items-center justify-center gap-2 rounded-xs border border-ink-900 bg-white px-5 text-sm font-semibold text-ink-900 hover:bg-ink-50"
        >
          <Package aria-hidden="true" className="size-4" />
          View cart
        </Link>
      </div>
    </div>
  );
}
