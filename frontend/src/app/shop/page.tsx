import type { Metadata } from "next";
import Link from "next/link";

import { Breadcrumbs } from "@/components/catalog/primitives";
import { Pagination, ProductGrid, ResultCount } from "@/components/catalog/ProductGrid";
import {
  ActiveFilterChips,
  FilterControls,
  SortSelect,
} from "@/components/filters/FilterControls";
import { Button, EmptyState, Section } from "@/components/ui";
import { getFacets, listCategories, listProducts } from "@/lib/api/catalog";
import { ApiError } from "@/lib/api/client";
import { activeChips, readFilters, toQuery, writeFilters } from "@/lib/filters";

// Rendered per request. Prices, stock and availability must never be baked
// into a build: a stale static page would sell a variant that has since sold
// out, at a price the catalogue has since changed.
export const dynamic = "force-dynamic";

export const metadata: Metadata = {
  title: "Shop all safety posters and sign boards",
  description:
    "The full Safety Poster Prints catalogue. Filter by category, material, size, price and availability. Boards priced per material and size, shipped across India.",
  alternates: { canonical: "/shop" },
};

/**
 * The shop.
 *
 * Server-rendered and URL-driven end to end. The page reads `searchParams`,
 * hands them to the API, and renders what came back. Filter interactions are
 * links and `router.push` with `scroll: false` - there is no client-side copy
 * of the product list, so the grid is always exactly what the database says.
 *
 * `searchParams` is a Promise in Next 16, so this page is async and every
 * filter change re-renders it on the server. That is the intent: the result set
 * must be crawlable and shareable, not only reachable by clicking.
 */
export default async function ShopPage({
  searchParams,
}: {
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}) {
  const raw = await searchParams;
  const params = new URLSearchParams();
  for (const [key, value] of Object.entries(raw)) {
    if (typeof value === "string") params.set(key, value);
    else if (Array.isArray(value)) for (const item of value) params.append(key, item);
  }

  const state = readFilters(params);
  const chips = activeChips(state);

  const [categories, facets] = await Promise.all([
    listCategories(),
    getFacets().catch(() => null),
  ]);

  if (!facets) {
    return (
      <Section>
        <div className="container-page">
          <EmptyState
            title="We couldn't load the catalogue"
            description="The store API did not respond. This is usually temporary. Please try again, or contact us on WhatsApp and we will take your order directly."
            action={
              <Button variant="primary" asChild={false} className="contents">
                <Link
                  href="/shop"
                  className="inline-flex h-11 items-center justify-center rounded-xs border border-ink-950 bg-signal-400 px-5 text-sm font-semibold text-ink-950 hover:bg-signal-300"
                >
                  Retry
                </Link>
              </Button>
            }
          />
        </div>
      </Section>
    );
  }

  const pageHref = (target: number) => {
    const query = writeFilters({ ...state, page: target });
    return query ? `/shop?${query}` : "/shop";
  };

  let products: Awaited<ReturnType<typeof listProducts>>;
  let failure: ApiError | null = null;
  try {
    products = await listProducts(toQuery(state));
  } catch (error) {
    failure = error instanceof ApiError ? error : new ApiError(0, {
      code: "network_error",
      message: "We couldn't reach the store.",
    });
    products = { items: [], meta: { page: 1, per_page: state.perPage, total: 0, total_pages: 0, has_next: false, has_previous: false } };
  }

  return (
    <Section className="pb-16">
      <div className="container-page">
        <Breadcrumbs items={[{ name: "Home", href: "/" }, { name: "Shop" }]} className="mb-4" />

        <header className="mb-6 border-b border-ink-200 pb-6">
          <h1 className="text-2xl sm:text-3xl">All safety products</h1>
          <p className="mt-2 max-w-2xl text-[15px] leading-relaxed text-ink-600">
            {categories.length} categories, priced by material and size. Filter to the exact board
            you need - the combination you pick is the combination that gets printed.
          </p>
        </header>

        <div className="flex flex-col gap-6 lg:flex-row">
          <FilterControls facets={facets} categories={categories} />

          <div className="min-w-0 flex-1">
            <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
              <ResultCount
                total={products.meta.total}
                page={products.meta.page}
                perPage={products.meta.per_page}
              />
              <SortSelect />
            </div>

            {chips.length > 0 ? (
              <div className="mb-5 lg:hidden">
                <ActiveFilterChips chips={chips} />
              </div>
            ) : null}

            {failure ? (
              <EmptyState
                title="We couldn't load products"
                description={
                  failure.isNetworkError
                    ? "The store could not be reached. Please check your connection and try again."
                    : failure.message
                }
                action={
                  <Button variant="outline" asChild={false} className="contents">
                    <Link
                      href={pageHref(1)}
                      className="inline-flex h-11 items-center justify-center rounded-xs border border-ink-300 bg-white px-5 text-sm font-semibold text-ink-900 hover:border-ink-900"
                    >
                      Try again
                    </Link>
                  </Button>
                }
              />
            ) : products.items.length === 0 ? (
              <EmptyState
                title="No products match your current filters"
                description="Try removing a filter, or browse the full catalogue. If you need a specific board that is not listed, ask us - we print to order."
                action={
                  <Button variant="outline" asChild={false} className="contents">
                    <Link
                      href="/shop"
                      className="inline-flex h-11 items-center justify-center rounded-xs border border-ink-300 bg-white px-5 text-sm font-semibold text-ink-900 hover:border-ink-900"
                    >
                      Clear all filters
                    </Link>
                  </Button>
                }
              />
            ) : (
              <>
                <ProductGrid products={products.items} />
                <Pagination meta={products.meta} buildHref={pageHref} />
              </>
            )}
          </div>
        </div>
      </div>
    </Section>
  );
}
