"use client";

/**
 * Primary navigation: desktop bar + mobile drawer.
 *
 * Accessibility notes, because a drawer is easy to get wrong:
 *   - the trigger is a real `<button>` with `aria-expanded` and `aria-controls`;
 *   - the drawer traps focus, closes on Escape, and returns focus to the
 *     trigger on close;
 *   - it is a labelled dialog with `aria-modal`, not a bare `<div>`;
 *   - background scroll is locked while open, and the layout is prevented from
 *     shifting when the scrollbar disappears.
 *
 * Category links are rendered from the database on the server and passed in.
 * The list is never hard-coded here.
 */

import * as DialogPrimitive from "@radix-ui/react-dialog";
import {
  ArrowRight,
  Building2,
  Factory,
  FlaskConical,
  Menu,
  Search,
  ShoppingBag,
  Truck,
  User,
  X,
} from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState } from "react";

import { Wordmark } from "@/components/layout/Wordmark";
import { CartCount } from "@/components/cart/CartCount";
import { Button } from "@/components/ui";
import { cn } from "@/lib/cn";

interface NavCategory {
  name: string;
  slug: string;
  count: number;
}

const UTILITY_LINKS = [
  { href: "/industries", label: "Industries" },
  { href: "/5s", label: "5S" },
  { href: "/msds", label: "MSDS" },
  { href: "/about", label: "About" },
  { href: "/contact", label: "Contact" },
];

export function SiteHeader({ categories }: { categories: NavCategory[] }) {
  const pathname = usePathname();

  // Any navigation must close the drawer, otherwise a link tap leaves the
  // overlay open over the page you just moved to.
  //
  // Done by *derivation* rather than with an effect: the open state records the
  // pathname it was opened at, so a pathname change makes `open` false on its
  // own. An effect that called setState on every navigation would be a second
  // render pass on every route change, and React's lint rules flag it for
  // exactly that reason.
  const [drawer, setDrawer] = useState<{ open: boolean; at: string }>({
    open: false,
    at: pathname,
  });
  const drawerOpen = drawer.open && drawer.at === pathname;
  const setDrawerOpen = (open: boolean) => setDrawer({ open, at: pathname });

  // The primary nav on desktop: five destinations, plus the search, account and
  // cart controls. Kept to one line's worth at the `lg` breakpoint of 1024px -
  // anything longer pushes the icons off-screen rather than wrapping.

  return (
    <header className="sticky top-0 z-50 border-b border-ink-200 bg-white/95 backdrop-blur supports-[backdrop-filter]:bg-white/90">
      <div className="container-page">
        <div className="flex h-14 items-center gap-3 sm:h-16 lg:gap-6">
          {/* --- mobile: menu trigger --- */}
          <DialogPrimitive.Root
            open={drawerOpen}
            onOpenChange={setDrawerOpen}
          >
            <DialogPrimitive.Trigger asChild>
              <Button
                variant="quiet"
                size="icon"
                className="-ml-2 lg:hidden"
                aria-label="Open menu"
              >
                <Menu aria-hidden="true" />
              </Button>
            </DialogPrimitive.Trigger>

            <DialogPrimitive.Portal>
              <DialogPrimitive.Overlay
                className={cn(
                  "fixed inset-0 z-50 bg-ink-950/50 backdrop-blur-[2px]",
                  "data-[state=open]:animate-in data-[state=open]:fade-in",
                )}
              />
              <DialogPrimitive.Content
                className={cn(
                  "fixed inset-y-0 left-0 z-50 flex w-[86%] max-w-sm flex-col",
                  "bg-white shadow-2xl outline-none",
                  "data-[state=open]:animate-in data-[state=open]:slide-in-from-left",
                )}
              >
                <DialogPrimitive.Title className="sr-only">
                  Site menu
                </DialogPrimitive.Title>
                <DialogPrimitive.Description className="sr-only">
                  Browse products, categories, industries and account pages.
                </DialogPrimitive.Description>

                <div className="flex h-14 shrink-0 items-center justify-between border-b border-ink-200 px-4">
                  <Link href="/" onClick={() => setDrawerOpen(false)}>
                    <Wordmark />
                  </Link>
                  <DialogPrimitive.Close asChild>
                    <Button variant="quiet" size="icon" aria-label="Close menu">
                      <X aria-hidden="true" />
                    </Button>
                  </DialogPrimitive.Close>
                </div>

                <nav
                  aria-label="Mobile"
                  className="flex-1 overflow-y-auto overscroll-contain px-4 py-4"
                >
                  <DrawerSection title="Shop">
                    <DrawerLink href="/shop" icon={<ShoppingBag aria-hidden="true" />}>
                      All products
                    </DrawerLink>
                    <DrawerLink href="/shop?sort=popular" icon={<Truck aria-hidden="true" />}>
                      Best selling
                    </DrawerLink>
                  </DrawerSection>

                  <DrawerSection title="Browse">
                    <DrawerLink href="/industries" icon={<Factory aria-hidden="true" />}>
                      Industries
                    </DrawerLink>
                    {UTILITY_LINKS.slice(1).map((link) => (
                      <DrawerLink
                        key={link.href}
                        href={link.href}
                        icon={
                          link.label === "MSDS" ? (
                            <FlaskConical aria-hidden="true" />
                          ) : link.label === "5S" ? (
                            <Building2 aria-hidden="true" />
                          ) : (
                            <ArrowRight aria-hidden="true" />
                          )
                        }
                      >
                        {link.label}
                      </DrawerLink>
                    ))}
                  </DrawerSection>

                  <DrawerSection title="Categories">
                    <ul className="space-y-0.5">
                      {categories.map((category) => (
                        <li key={category.slug}>
                          <Link
                            href={`/category/${category.slug}`}
                            onClick={() => setDrawerOpen(false)}
                            className="flex items-center justify-between rounded-xs px-2 py-2 text-sm text-ink-700 hover:bg-ink-50 hover:text-ink-950"
                          >
                            <span>{category.name}</span>
                            <span className="tabular text-xs text-ink-400">
                              {category.count}
                            </span>
                          </Link>
                        </li>
                      ))}
                    </ul>
                  </DrawerSection>

                  <DrawerSection title="Account">
                    <DrawerLink href="/account" icon={<User aria-hidden="true" />}>
                      My account
                    </DrawerLink>
                    <DrawerLink href="/account/wishlist" icon={<ShoppingBag aria-hidden="true" />}>
                      Wishlist
                    </DrawerLink>
                    <DrawerLink href="/cart" icon={<Truck aria-hidden="true" />}>
                      Cart
                    </DrawerLink>
                  </DrawerSection>
                </nav>

                <div className="shrink-0 border-t border-ink-200 p-4">
                  <DialogPrimitive.Close asChild>
                    <Link
                      href="/bulk-order"
                      className="inline-flex h-11 w-full items-center justify-center rounded-xs border border-ink-950 bg-signal-400 px-5 text-sm font-semibold text-ink-950 transition-colors hover:bg-signal-300"
                    >
                      Request a bulk quote
                    </Link>
                  </DialogPrimitive.Close>
                </div>
              </DialogPrimitive.Content>
            </DialogPrimitive.Portal>
          </DialogPrimitive.Root>

          {/* --- wordmark --- */}
          <Link
            href="/"
            className="shrink-0 rounded-xs"
            aria-label="Safety Poster Prints, home"
          >
            <Wordmark />
          </Link>

          {/* --- desktop navigation --- */}
          {/*
            Short by design. An earlier version promoted the five key categories
            into this row, giving eleven links. At the `lg` breakpoint of 1024px
            that pushed the search, account and cart icons 220px off the right
            edge of the screen. Those five categories are already the most
            prominent items in the rail directly below, so repeating them here
            bought nothing and cost the layout.
          */}
          <nav
            aria-label="Primary"
            className="hidden min-w-0 flex-1 items-center gap-0.5 lg:flex"
          >
            <NavLink href="/shop">Products</NavLink>
            <NavLink href="/category">Categories</NavLink>
            {UTILITY_LINKS.map((link) => (
              <NavLink key={link.href} href={link.href}>
                {link.label}
              </NavLink>
            ))}
          </nav>

          <div className="ml-auto flex items-center gap-1 lg:gap-2">
            <Link
              href="/search"
              aria-label="Search products"
              className="inline-flex size-10 items-center justify-center rounded-xs text-ink-800 hover:bg-ink-100"
            >
              <Search aria-hidden="true" className="size-[18px]" />
            </Link>

            <Link
              href="/account"
              aria-label="Account"
              className="hidden size-10 items-center justify-center rounded-xs text-ink-800 hover:bg-ink-100 sm:inline-flex"
            >
              <User aria-hidden="true" className="size-[18px]" />
            </Link>

            <Link
              href="/cart"
              aria-label="Cart"
              className="relative inline-flex size-10 items-center justify-center rounded-xs text-ink-800 hover:bg-ink-100"
            >
              <ShoppingBag aria-hidden="true" className="size-[18px]" />
              <CartCount />
            </Link>
          </div>
        </div>
      </div>

      {/*
        One category row, not two.

        An earlier version had a bold "key categories" strip above a full rail
        of all 18. It looked thorough and was actively harmful: four stacked
        header rows on a 1440px screen, and the rail clipped mid-word at the
        right edge with nothing indicating it scrolled. One row, scannable, with
        a fade to signal that it continues.

        On a laptop the 18 names still overflow, so this stays a scroll rail with
        `no-scrollbar`; the gradient overlay is the affordance.
      */}
      <nav
        aria-label="Categories"
        className="relative hidden border-t border-ink-100 bg-ink-50/60 lg:block"
      >
        <div className="container-page flex h-9 items-center gap-1 overflow-x-auto no-scrollbar">
          {categories.map((category) => (
            <Link
              key={category.slug}
              href={`/category/${category.slug}`}
              // `prefetch={false}` is deliberate, not an oversight. Next
              // prefetches a visible <Link> on hover/viewport, and this rail
              // holds 18 of them plus a footer holding dozens more. Measured on
              // /shop: 98 requests, and a filtered page took 26 seconds to
              // settle because prefetches kept the network busy continuously.
              // A shopper clicks one or two of these at most; pre-downloading
              // the other sixteen is pure waste, and on mobile it competes with
              // the product images for bandwidth.
              prefetch={false}
              className="flex shrink-0 items-center gap-1.5 rounded-xs px-2.5 py-1 text-[13px] font-medium text-ink-700 transition-colors hover:bg-white hover:text-ink-950"
            >
              {category.name}
              <span className="tabular text-[11px] text-ink-400">{category.count}</span>
            </Link>
          ))}
          <span className="shrink-0 pl-3 text-[12px] text-ink-400">
            {categories.length} categories
          </span>
        </div>
        {/* Right-edge fade: says "there is more" without adding a control. */}
        <div
          aria-hidden="true"
          className="pointer-events-none absolute inset-y-0 right-0 w-12 bg-gradient-to-l from-ink-50 to-transparent"
        />
      </nav>
    </header>
  );
}

function NavLink({
  href,
  children,
}: {
  href: string;
  children: React.ReactNode;
}) {
  const pathname = usePathname();
  const active = pathname === href || pathname.startsWith(`${href}/`);
  return (
    <Link
      href={href}
      aria-current={active ? "page" : undefined}
      className={cn(
        "rounded-xs px-2.5 py-2 text-[14px] font-semibold transition-colors",
        active ? "text-ink-950" : "text-ink-600 hover:text-ink-950",
      )}
    >
      {children}
    </Link>
  );
}

function DrawerSection({
  title,
  children,
}: {
  title: string;
  children: React.ReactNode;
}) {
  return (
    <div className="border-b border-ink-100 py-4 first:pt-0 last:border-0">
      <p className="eyebrow mb-2 px-2">{title}</p>
      <div className="space-y-0.5">{children}</div>
    </div>
  );
}

function DrawerLink({
  href,
  icon,
  children,
}: {
  href: string;
  icon: React.ReactNode;
  children: React.ReactNode;
}) {
  return (
    <Link
      href={href}
      className="flex items-center gap-3 rounded-xs px-2 py-2.5 text-[15px] font-medium text-ink-800 hover:bg-ink-50"
    >
      <span className="text-ink-400 [&_svg]:size-[18px]">{icon}</span>
      {children}
    </Link>
  );
}
