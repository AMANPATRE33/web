import type { Metadata } from "next";
import Link from "next/link";

import { Breadcrumbs } from "@/components/catalog/primitives";
import { ProductGrid } from "@/components/catalog/ProductGrid";
import { EmptyState, Section } from "@/components/ui";
import { listCategories, listProducts } from "@/lib/api/catalog";
import { env } from "@/lib/env";

// Rendered per request. Prices, stock and availability must never be baked
// into a build: a stale static page would sell a variant that has since sold
// out, at a price the catalogue has since changed.
export const dynamic = "force-dynamic";

export const metadata: Metadata = {
  title: "All product categories",
  description:
    "Every safety signage category at Safety Poster Prints: electrical safety, fire safety, MSDS, road safety, PPE and more. Filter by material, size and price.",
  alternates: { canonical: "/category" },
};

/**
 * Category index.
 *
 * Lists every category the database knows about with its real product count.
 * A category with a genuine zero count is rendered as disabled rather than
 * hidden - a shopper comparing categories should be able to see that a category
 * exists and is empty, not silently lose it.
 */
export default async function CategoryIndexPage() {
  const categories = await listCategories();

  const withCounts = await Promise.all(
    categories.map(async (category) => {
      const page = await listProducts({
        category: [category.slug],
        per_page: 4,
        sort: "popular",
      }).catch(() => null);
      return {
        category,
        products: page?.items ?? [],
        count: page?.meta.total ?? category.product_count,
      };
    }),
  );

  const jsonLd = {
    "@context": "https://schema.org",
    "@type": "CollectionPage",
    name: "Product categories",
    url: `${env.siteUrl}/category`,
    mainEntity: {
      "@type": "ItemList",
      numberOfItems: categories.length,
      itemListElement: categories.map((category, index) => ({
        "@type": "ListItem",
        position: index + 1,
        name: category.name,
        url: `${env.siteUrl}/category/${category.slug}`,
      })),
    },
  };

  return (
    <Section className="pb-16">
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: JSON.stringify(jsonLd) }}
      />
      <div className="container-page">
        <Breadcrumbs
          items={[{ name: "Home", href: "/" }, { name: "Categories" }]}
          className="mb-4"
        />
        <header className="mb-8">
          <h1 className="text-2xl sm:text-3xl">Product categories</h1>
          <p className="mt-2 max-w-2xl text-[15px] leading-relaxed text-ink-600">
            {categories.length} categories covering industrial, workplace and public-area safety
            signage. Every category is priced by material and size.
          </p>
        </header>

        {categories.length === 0 ? (
          <EmptyState
            title="No categories found"
            description="The catalogue could not be loaded. Please try again shortly."
          />
        ) : (
          <ul className="space-y-6">
            {withCounts.map(({ category, products, count }) => (
              <li
                key={category.id}
                className="grid gap-5 border border-ink-200 p-5 lg:grid-cols-[280px_1fr]"
              >
                <div className="min-w-0">
                  <h2 className="text-lg">
                    {count > 0 ? (
                      <Link
                        href={`/category/${category.slug}`}
                        className="hover:underline"
                      >
                        {category.name}
                      </Link>
                    ) : (
                      <span className="text-ink-500">{category.name}</span>
                    )}
                  </h2>
                  <p className="tabular mt-1 text-[13px] text-ink-500">
                    {count} product{count === 1 ? "" : "s"}
                  </p>
                  {category.description ? (
                    <p className="mt-3 text-[13px] leading-relaxed text-ink-600">
                      {category.description}
                    </p>
                  ) : null}
                  {count > 0 ? (
                    <Link
                      href={`/category/${category.slug}`}
                      className="mt-4 inline-flex h-10 items-center justify-center rounded-xs border border-ink-900 bg-white px-4 text-[13px] font-semibold text-ink-900 transition-colors hover:bg-ink-50"
                    >
                      View all {count}
                    </Link>
                  ) : (
                    <p className="mt-4 text-[12px] italic text-ink-400">
                      No products listed in this category yet.
                    </p>
                  )}
                </div>

                {products.length > 0 ? (
                  <div className="min-w-0">
                    <ProductGrid products={products} priorityCount={2} />
                  </div>
                ) : (
                  <div className="flex items-center justify-center border border-dashed border-ink-300 bg-ink-50 p-6 text-center">
                    <p className="text-[13px] text-ink-500">
                      Nothing listed yet. This category exists and is ready for content.
                    </p>
                  </div>
                )}
              </li>
            ))}
          </ul>
        )}
      </div>
    </Section>
  );
}
