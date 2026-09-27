import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";

import { Breadcrumbs } from "@/components/catalog/primitives";
import { Pagination, ProductGrid, ResultCount } from "@/components/catalog/ProductGrid";
import {
  ActiveFilterChips,
  FilterControls,
  SortSelect,
} from "@/components/filters/FilterControls";
import { Button, EmptyState, Section } from "@/components/ui";
import { getCategory, getFacets, listCategories, listProducts } from "@/lib/api/catalog";
import { ApiError } from "@/lib/api/client";
import { env } from "@/lib/env";
import { activeChips, readFilters, toQuery, writeFilters } from "@/lib/filters";

/**
 * Category landing page.
 *
 * The slug in the URL is the SEO slug exactly as stored in the database. That
 * matters: one category's stored slug is misspelled (`envirnomental-signages`,
 * the original Wix slug). The *display* name is corrected to "Environmental
 * Signages" and the URL is not, because changing a live URL loses the ranking
 * and breaks every existing link. A test in the backend pins the stored slug so
 * this cannot be "tidied up" by accident.
 */

// Rendered per request. Prices, stock and availability must never be baked
// into a build: a stale static page would sell a variant that has since sold
// out, at a price the catalogue has since changed.
export const dynamic = "force-dynamic";

export async function generateStaticParams() {
  try {
    const categories = await listCategories();
    return categories.map((category) => ({ slug: category.slug }));
  } catch {
    // Pre-render must not fail the build because the API is down; the page is
    // fully dynamic and will render on demand.
    return [];
  }
}

export async function generateMetadata({
  params,
}: {
  params: Promise<{ slug: string }>;
}): Promise<Metadata> {
  const { slug } = await params;
  try {
    const category = await getCategory(slug);
    const description =
      category.seo_description ??
      category.description ??
      `Shop ${category.product_count} ${category.name} from Safety Poster Prints. Filter by material, size and price. Shipped across India.`;

    return {
      title: category.seo_title ?? `${category.name} - ${category.product_count} products`,
      description,
      alternates: { canonical: `/category/${category.slug}` },
      openGraph: {
        title: `${category.name} | Safety Poster Prints`,
        description,
        url: `${env.siteUrl}/category/${category.slug}`,
        type: "website",
      },
    };
  } catch (error) {
    // See the note in `products/[slug]/page.tsx`: calling notFound() from
    // metadata, rather than only from the body, is what yields a real 404
    // status instead of a soft one.
    if (error instanceof ApiError && error.isNotFound) notFound();
    throw error;
  }
}

export default async function CategoryPage({
  params,
  searchParams,
}: {
  params: Promise<{ slug: string }>;
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}) {
  const { slug } = await params;
  const raw = await searchParams;
  const query = new URLSearchParams();
  for (const [key, value] of Object.entries(raw)) {
    if (typeof value === "string") query.set(key, value);
    else if (Array.isArray(value)) for (const item of value) query.append(key, item);
  }

  const state = readFilters(query);
  // The category is fixed by the route, so a `category` param in the URL is
  // ignored rather than allowed to widen or contradict the page.
  const scoped = { ...state, category: [slug] };
  const chips = activeChips(state);

  let category;
  try {
    category = await getCategory(slug);
  } catch (error) {
    if (error instanceof ApiError && error.isNotFound) notFound();
    throw error;
  }

  const [facets, allCategories] = await Promise.all([
    getFacets(slug).catch(() => null),
    listCategories().catch(() => []),
  ]);

  const pageHref = (target: number) => {
    const next = writeFilters({ ...scoped, page: target });
    return next ? `/category/${slug}?${next}` : `/category/${slug}`;
  };

  const products = facets
    ? await listProducts(toQuery(scoped)).catch(() => null)
    : null;

  const breadcrumbJsonLd = {
    "@context": "https://schema.org",
    "@type": "BreadcrumbList",
    itemListElement: [
      { "@type": "ListItem", position: 1, name: "Home", item: env.siteUrl },
      { "@type": "ListItem", position: 2, name: "Shop", item: `${env.siteUrl}/shop` },
      { "@type": "ListItem", position: 3, name: category.name, item: `${env.siteUrl}/category/${slug}` },
    ],
  };

  const siblings = allCategories.filter((entry) => entry.id !== category.id && entry.product_count > 0);

  return (
    <Section className="pb-16">
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: JSON.stringify(breadcrumbJsonLd) }}
      />
      <div className="container-page">
        <Breadcrumbs
          items={[
            { name: "Home", href: "/" },
            { name: "Shop", href: "/shop" },
            { name: category.name },
          ]}
          className="mb-4"
        />

        <header className="mb-6 border-b border-ink-200 pb-6">
          <h1 className="text-2xl sm:text-3xl">{category.name}</h1>
          {category.description ? (
            <p className="mt-3 max-w-3xl text-[15px] leading-relaxed text-ink-600">
              {category.description}
            </p>
          ) : null}
          <p className="mt-3 text-[13px] text-ink-500">
            {category.product_count} product{category.product_count === 1 ? "" : "s"} in this
            category
            {facets ? (
              <>
                {" "}
                &middot; {facets.materials.length} materials
                {facets.sizes.length > 0 ? `, ${facets.sizes.length} sizes available` : null}
              </>
            ) : null}
          </p>
        </header>

        {siblings.length > 0 ? (
          <nav aria-label="Other categories" className="mb-6">
            <p className="eyebrow mb-2">Other categories</p>
            <ul className="flex flex-wrap gap-2">
              {siblings.map((entry) => (
                <li key={entry.id}>
                  <Link
                    href={`/category/${entry.slug}`}
                    className="inline-flex items-center gap-1.5 rounded-xs border border-ink-300 bg-white px-3 py-1.5 text-[13px] font-medium text-ink-800 transition-colors hover:border-ink-900 hover:bg-ink-50"
                  >
                    {entry.name}
                    <span className="tabular text-[11px] text-ink-400">{entry.product_count}</span>
                  </Link>
                </li>
              ))}
            </ul>
          </nav>
        ) : null}

        <div className="flex flex-col gap-6 lg:flex-row">
          {facets ? (
            <FilterControls
              facets={facets}
              categories={allCategories}
              hideCategory
              lockedCategorySlug={slug}
            />
          ) : null}

          <div className="min-w-0 flex-1">
            <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
              <ResultCount
                total={products?.meta.total ?? 0}
                page={products?.meta.page ?? 1}
                perPage={products?.meta.per_page ?? state.perPage}
              />
              <SortSelect />
            </div>

            {chips.length > 0 ? (
              <div className="mb-5 lg:hidden">
                <ActiveFilterChips chips={chips} />
              </div>
            ) : null}

            {!products ? (
              <EmptyState
                title="We couldn't load products"
                description="The store API did not respond. Please try again in a moment."
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
                description={`Nothing in ${category.name} matches those filters. Try widening the size or material, or clear the filters to see everything.`}
                action={
                  <Button variant="outline" asChild={false} className="contents">
                    <Link
                      href={`/category/${slug}`}
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
