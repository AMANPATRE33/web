import type { Metadata } from "next";
import Link from "next/link";
import { Search as SearchIcon } from "lucide-react";

import { ProductImage } from "@/components/catalog/ProductImage";
import { Breadcrumbs, Price, StockBadge } from "@/components/catalog/primitives";
import { Pagination } from "@/components/catalog/ProductGrid";
import { SearchBox } from "@/components/search/SearchBox";
import { Button, EmptyState, Section } from "@/components/ui";
import { searchCatalogue } from "@/lib/api/catalog";
import { env } from "@/lib/env";

// Rendered per request. Prices, stock and availability must never be baked
// into a build: a stale static page would sell a variant that has since sold
// out, at a price the catalogue has since changed.
export const dynamic = "force-dynamic";

export const metadata: Metadata = {
  title: "Search safety posters and sign boards",
  description:
    "Search the Safety Poster Prints catalogue by product name, category, SKU, material, size or description.",
  alternates: { canonical: "/search" },
  robots: { index: false, follow: true },
};

/**
 * Search results.
 *
 * Backed by `/api/v1/search`, which searches product titles, descriptions,
 * SKUs, category names, material and size attributes and tags. Results are
 * server-rendered from `?q=`, so a search result page is a real URL.
 *
 * This route is `noindex`: a query-string result page has no standalone value in
 * an index and would otherwise generate near-infinite thin pages.
 */
export default async function SearchPage({
  searchParams,
}: {
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}) {
  const raw = await searchParams;
  const query = typeof raw.q === "string" ? raw.q.trim() : "";
  const page = Math.max(1, Number.parseInt(String(raw.page ?? "1"), 10) || 1);
  const perPage = 24;

  const results = query.length > 0
    ? await searchCatalogue(query, { page, perPage }).catch(() => null)
    : null;

  const pageHref = (target: number) =>
    `/search?q=${encodeURIComponent(query)}${target > 1 ? `&page=${target}` : ""}`;

  const jsonLd =
    results && results.count > 0
      ? {
          "@context": "https://schema.org",
          "@type": "SearchResultsPage",
          name: `Search: ${query}`,
          url: `${env.siteUrl}/search?q=${encodeURIComponent(query)}`,
          mainEntity: {
            "@type": "ItemList",
            numberOfItems: results.count,
            itemListElement: results.items.slice(0, perPage).map((item, index) => ({
              "@type": "ListItem",
              position: index + 1,
              url: `${env.siteUrl}${
                item.type === "category" ? `/category/${item.slug}` : `/products/${item.slug}`
              }`,
              name: item.title,
            })),
          },
        }
      : null;

  return (
    <Section className="pb-16">
      {jsonLd ? (
        <script
          type="application/ld+json"
          dangerouslySetInnerHTML={{ __html: JSON.stringify(jsonLd) }}
        />
      ) : null}

      <div className="container-page">
        <Breadcrumbs
          items={[{ name: "Home", href: "/" }, { name: "Search" }]}
          className="mb-4"
        />

        <header className="mb-8">
          <h1 className="text-2xl sm:text-3xl">Search</h1>
          <p className="mt-2 max-w-2xl text-[15px] text-ink-600">
            Search by product name, category, SKU, material or size. SKU searches are useful when
            you have a quote in front of you.
          </p>
          <SearchBox
            initialQuery={query}
            autoFocus={query.length === 0}
            className="mt-5 max-w-2xl"
          />
        </header>

        {query.length === 0 ? (
          <EmptyState
            icon={<SearchIcon aria-hidden="true" className="size-10" />}
            title="What are you looking for?"
            description="Try a hazard name like “high voltage”, a material like “3MM ACP”, a size like “18x24”, or a full SKU from a quotation."
            action={
              <div className="flex flex-wrap justify-center gap-2">
                {["high voltage", "MSDS", "3MM ACP", "5S"].map((term) => (
                  <Button key={term} variant="outline" asChild>
                    <Link href={`/search?q=${encodeURIComponent(term)}`}>{term}</Link>
                  </Button>
                ))}
              </div>
            }
          />
        ) : results === null ? (
          <EmptyState
            title="We couldn't run that search"
            description="The search service did not respond. Please try again in a moment."
            action={
              <Button variant="outline" asChild>
                <Link href={`/search?q=${encodeURIComponent(query)}`}>Try again</Link>
              </Button>
            }
          />
        ) : results.count === 0 ? (
          <EmptyState
            title={`No results for “${query}”`}
            description="Check the spelling, try a broader term, or browse the catalogue by category. If you need a specific board that is not listed, ask us - most boards can be printed to order."
            action={
              <div className="flex flex-wrap justify-center gap-2">
                <Button variant="primary" asChild>
                  <Link href="/shop">Browse all products</Link>
                </Button>
                <Button variant="outline" asChild>
                  <Link href="/bulk-order">Request a board</Link>
                </Button>
              </div>
            }
          />
        ) : (
          <>
            <p className="mb-5 text-[13px] text-ink-600">
              <span className="font-semibold text-ink-950">{results.count}</span> result
              {results.count === 1 ? "" : "s"} for{" "}
              <span className="font-semibold text-ink-950">“{query}”</span>
            </p>

            <ul className="divide-y divide-ink-200 border-y border-ink-200">
              {results.items.map((item) => (
                <li key={`${item.type}-${item.id}`}>
                  <Link
                    href={
                      item.type === "category"
                        ? `/category/${item.slug}`
                        : `/products/${item.slug}`
                    }
                    className="flex items-center gap-4 py-4 transition-colors hover:bg-ink-50"
                  >
                    <ProductImage
                      src={item.image_url}
                      alt={item.title}
                      width={72}
                      height={72}
                      sizes="72px"
                      className="size-16 shrink-0 border border-ink-200 p-1.5 sm:size-20 sm:p-2"
                    />
                    <div className="min-w-0 flex-1">
                      <p className="text-[11px] font-medium uppercase tracking-[0.06em] text-ink-500">
                        {item.type === "category" ? "Category" : "Product"}
                      </p>
                      <p className="mt-0.5 text-[15px] font-semibold leading-snug text-ink-950">
                        {item.title}
                      </p>
                      {item.subtitle ? (
                        <p className="mt-0.5 line-clamp-1 text-[13px] text-ink-600">
                          {item.subtitle}
                        </p>
                      ) : null}
                    </div>
                    <div className="shrink-0 text-right">
                      {item.price ? <Price price={item.price} size="sm" /> : null}
                      <div className="mt-1.5">
                        <StockBadge status={item.in_stock ? "in_stock" : "out_of_stock"} />
                      </div>
                    </div>
                  </Link>
                </li>
              ))}
            </ul>

            <Pagination meta={results.meta} buildHref={pageHref} />
          </>
        )}
      </div>
    </Section>
  );
}
