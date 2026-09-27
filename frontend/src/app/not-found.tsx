import Link from "next/link";
import { Search } from "lucide-react";

import { SearchBox } from "@/components/search/SearchBox";
import { Button } from "@/components/ui";

export default function NotFound() {
  return (
    <div className="container-page flex min-h-[70vh] flex-col items-center justify-center py-20 text-center">
      <p className="eyebrow">404</p>
      <h1 className="mt-3 text-2xl sm:text-3xl">We couldn&apos;t find that page</h1>
      <p className="mt-3 max-w-lg text-[15px] leading-relaxed text-ink-600">
        The link may be old, or the product may have been renamed. Search for what you were
        looking for &mdash; searching by SKU works too, if you have a quotation in front of you.
      </p>

      <div className="mt-7 w-full max-w-xl">
        <SearchBox size="md" autoFocus />
      </div>

      <div className="mt-7 flex flex-wrap justify-center gap-3">
        <Button variant="primary" asChild>
          <Link href="/shop">
            <Search aria-hidden="true" />
            Browse all products
          </Link>
        </Button>
        <Button variant="outline" asChild>
          <Link href="/contact">Contact us</Link>
        </Button>
      </div>

      <nav aria-label="Popular sections" className="mt-10">
        <p className="eyebrow mb-3">Popular sections</p>
        <ul className="flex flex-wrap justify-center gap-2">
          {[
            { href: "/category", label: "Categories" },
            { href: "/industries", label: "Industries" },
            { href: "/msds", label: "MSDS boards" },
            { href: "/5s", label: "5S" },
            { href: "/bulk-order", label: "Bulk order" },
            { href: "/blog", label: "Guides" },
          ].map((link) => (
            <li key={link.href}>
              <Link
                href={link.href}
                className="inline-block rounded-xs border border-ink-300 px-3 py-1.5 text-[13px] font-medium text-ink-700 transition-colors hover:border-ink-900 hover:text-ink-950"
              >
                {link.label}
              </Link>
            </li>
          ))}
        </ul>
      </nav>
    </div>
  );
}
