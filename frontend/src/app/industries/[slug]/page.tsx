import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";

import { Breadcrumbs } from "@/components/catalog/primitives";
import { ProductGrid } from "@/components/catalog/ProductGrid";
import { Markdown } from "@/components/content/Markdown";
import { Button, EmptyState, Section } from "@/components/ui";
import { ApiError } from "@/lib/api/client";
import { getIndustry, listIndustries } from "@/lib/api/content";
import { listProducts } from "@/lib/api/catalog";
import { env } from "@/lib/env";

// Rendered per request. Prices, stock and availability must never be baked
// into a build: a stale static page would sell a variant that has since sold
// out, at a price the catalogue has since changed.
export const dynamic = "force-dynamic";

export async function generateStaticParams() {
  try {
    const industries = await listIndustries();
    return industries.map((industry) => ({ slug: industry.slug }));
  } catch {
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
    const industry = await getIndustry(slug);
    const description =
      industry.seo_description ??
      industry.summary ??
      `Safety posters and sign boards for the ${industry.name.toLowerCase()} sector. Filter by material, size and price. Shipped across India.`;

    return {
      title: industry.seo_title ?? `${industry.name} safety signage`,
      description,
      alternates: { canonical: `/industries/${industry.slug}` },
      openGraph: {
        type: "article",
        title: `${industry.name} safety signage | Safety Poster Prints`,
        description,
        url: `${env.siteUrl}/industries/${industry.slug}`,
      },
    };
  } catch (error) {
    // See `products/[slug]/page.tsx`: notFound() from metadata is what sets a
    // real 404 status rather than a soft one.
    if (error instanceof ApiError && error.isNotFound) notFound();
    throw error;
  }
}

export default async function IndustryPage({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params;

  let industry;
  try {
    industry = await getIndustry(slug);
  } catch (error) {
    if (error instanceof ApiError && error.isNotFound) notFound();
    throw error;
  }

  // The industry page links specific products by slug rather than embedding
  // card objects, so the cards come from the catalogue API in a single
  // request. `slug` is an array filter that returns results in the given order,
  // which is what preserves the editor's curated sequence.
  const picks = industry.product_slugs.length
    ? (
        await listProducts({
          slug: industry.product_slugs.slice(0, 24),
          per_page: 24,
        }).catch(() => null)
      )?.items ?? []
    : [];

  const jsonLd = {
    "@context": "https://schema.org",
    "@type": "CollectionPage",
    name: `${industry.name} safety signage`,
    description: industry.seo_description ?? industry.summary ?? industry.tagline ?? undefined,
    url: `${env.siteUrl}/industries/${industry.slug}`,
    isPartOf: {
      "@type": "WebSite",
      name: "Safety Poster Prints",
      url: env.siteUrl,
    },
  };

  const breadcrumbJsonLd = {
    "@context": "https://schema.org",
    "@type": "BreadcrumbList",
    itemListElement: [
      { "@type": "ListItem", position: 1, name: "Home", item: env.siteUrl },
      { "@type": "ListItem", position: 2, name: "Industries", item: `${env.siteUrl}/industries` },
      { "@type": "ListItem", position: 3, name: industry.name },
    ],
  };

  const faqJsonLd =
    industry.product_count > 0
      ? {
          "@context": "https://schema.org",
          "@type": "FAQPage",
          mainEntity: [
            {
              "@type": "Question",
              name: `Which safety signage does a ${industry.name.toLowerCase()} site need?`,
              acceptedAnswer: {
                "@type": "Answer",
                text:
                  industry.summary ??
                  `A ${industry.name.toLowerCase()} site normally needs hazard communication boards, mandatory PPE signage and emergency exit boards. Our ${industry.name.toLowerCase()} collection covers ${industry.product_count} products across the standard materials and sizes.`,
              },
            },
          ],
        }
      : null;

  return (
    <Section className="pb-16">
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: JSON.stringify(jsonLd) }}
      />
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: JSON.stringify(breadcrumbJsonLd) }}
      />
      {faqJsonLd ? (
        <script
          type="application/ld+json"
          dangerouslySetInnerHTML={{ __html: JSON.stringify(faqJsonLd) }}
        />
      ) : null}

      <div className="container-page">
        <Breadcrumbs
          items={[
            { name: "Home", href: "/" },
            { name: "Industries", href: "/industries" },
            { name: industry.name },
          ]}
          className="mb-4"
        />

        <header className="mb-8 border-b border-ink-200 pb-6">
          <p className="eyebrow">{industry.tagline ?? "Industry collection"}</p>
          <h1 className="mt-2 text-2xl sm:text-3xl">{industry.name} safety signage</h1>
          {industry.summary ? (
            <p className="mt-3 max-w-3xl text-[15px] leading-relaxed text-ink-600">
              {industry.summary}
            </p>
          ) : null}
          <p className="mt-3 text-[13px] text-ink-500">
            {industry.product_count} recommended product
            {industry.product_count === 1 ? "" : "s"}
          </p>
        </header>

        <div className="grid gap-10 lg:grid-cols-[1fr_320px] lg:items-start">
          <div className="min-w-0">
            {industry.body ? <Markdown source={industry.body} /> : null}

            {picks.length > 0 ? (
              <section className="mt-10 border-t border-ink-200 pt-10">
                <h2 className="mb-6 text-lg">
                  Recommended for {industry.name.toLowerCase()}
                </h2>
                <ProductGrid products={picks} priorityCount={4} />
              </section>
            ) : (
              <div className="mt-8">
                <EmptyState
                  title="No products linked to this industry yet"
                  description="The industry page is published but the recommended product set has not been assigned. Browse the full catalogue in the meantime."
                  action={
                    <Button variant="primary" asChild>
                      <Link href="/shop">Browse all products</Link>
                    </Button>
                  }
                />
              </div>
            )}
          </div>

          <aside className="space-y-4 lg:sticky lg:top-32">
            <div className="border border-ink-200 bg-ink-50 p-5">
              <h2 className="text-[15px] font-bold text-ink-950">Ordering for a site?</h2>
              <p className="mt-2 text-[13px] leading-relaxed text-ink-600">
                Send your board list and we will quote freight and volume pricing properly.
              </p>
              <Link
                href="/bulk-order"
                className="mt-4 inline-flex h-10 w-full items-center justify-center rounded-xs border border-ink-950 bg-signal-400 px-4 text-[13px] font-bold text-ink-950 transition-colors hover:bg-signal-300"
              >
                Request a bulk quote
              </Link>
            </div>

            <div className="border border-ink-200 p-5">
              <h2 className="text-[15px] font-bold text-ink-950">Other industries</h2>
              <ul className="mt-3 space-y-1.5">
                {(
                  await listIndustries()
                    .then((all) => all.filter((entry) => entry.slug !== industry.slug).slice(0, 8))
                    .catch(() => [])
                ).map((entry) => (
                  <li key={entry.id}>
                    <Link
                      href={`/industries/${entry.slug}`}
                      className="text-[13px] text-ink-700 hover:text-ink-950 hover:underline"
                    >
                      {entry.name}
                    </Link>
                  </li>
                ))}
              </ul>
              <Link
                href="/industries"
                className="mt-3 inline-block text-[13px] font-semibold text-ink-900 underline underline-offset-4"
              >
                View all industries
              </Link>
            </div>
          </aside>
        </div>
      </div>
    </Section>
  );
}
