import type { Metadata } from "next";
import Link from "next/link";
import { ArrowRight, Building2 } from "lucide-react";

import { Breadcrumbs } from "@/components/catalog/primitives";
import { Button, EmptyState, Section } from "@/components/ui";
import { listIndustries } from "@/lib/api/content";


// Rendered per request. Prices, stock and availability must never be baked
// into a build: a stale static page would sell a variant that has since sold
// out, at a price the catalogue has since changed.
export const dynamic = "force-dynamic";

export const metadata: Metadata = {
  title: "Safety signage by industry",
  description:
    "Safety posters and sign boards organised by sector: manufacturing, chemical, construction, warehouse, office, laboratory, hospital and more.",
  alternates: { canonical: "/industries" },
};

/**
 * Industries index.
 *
 * Driven by `/api/v1/industries`. The only hand-written content here is the
 * empty state, which exists because a failed fetch and an empty table are
 * genuinely different things and should not look the same to a user.
 */
export default async function IndustriesPage() {
  const industries = await listIndustries().catch(() => null);

  return (
    <Section className="pb-16">
      <div className="container-page">
        <Breadcrumbs
          items={[{ name: "Home", href: "/" }, { name: "Industries" }]}
          className="mb-4"
        />
        <header className="mb-8">
          <p className="eyebrow">By sector</p>
          <h1 className="mt-2 text-2xl sm:text-3xl">Safety signage by industry</h1>
          <p className="mt-3 max-w-2xl text-[15px] leading-relaxed text-ink-600">
            Start from the hazards your sector is actually inspected on. Each industry page lists
            the boards normally required and links straight to the products.
          </p>
        </header>

        {!industries ? (
          <EmptyState
            icon={<Building2 aria-hidden="true" className="size-10" />}
            title="We couldn't load the industry pages"
            description="The content service did not respond. Please try again shortly, or browse the full catalogue in the meantime."
            action={
              <div className="flex flex-wrap justify-center gap-2">
                <Button variant="primary" asChild>
                  <Link href="/shop">Browse all products</Link>
                </Button>
                <Button variant="outline" asChild>
                  <Link href="/bulk-order">Ask for a shortlist</Link>
                </Button>
              </div>
            }
          />
        ) : industries.length === 0 ? (
          <EmptyState
            title="No industries published yet"
            description="Industry pages will appear here once the content is in place."
          />
        ) : (
          <ul className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {industries.map((industry) => (
              <li key={industry.id}>
                <Link
                  href={`/industries/${industry.slug}`}
                  className="group flex h-full flex-col border border-ink-200 bg-white p-5 transition-[border-color,box-shadow] hover:border-ink-900 hover:shadow-[0_2px_12px_rgba(11,13,16,0.08)]"
                >
                  <h2 className="text-[16px] font-semibold text-ink-950 group-hover:underline">
                    {industry.name}
                  </h2>
                  {industry.tagline ? (
                    <p className="mt-1.5 text-[12px] font-medium uppercase tracking-wide text-signal-600">
                      {industry.tagline}
                    </p>
                  ) : null}
                  {industry.summary ? (
                    <p className="mt-2.5 text-[13px] leading-relaxed text-ink-600">
                      {industry.summary}
                    </p>
                  ) : null}
                  <p className="mt-auto flex items-center justify-between pt-5 text-[12px] text-ink-500">
                    <span className="tabular">
                      {industry.product_count} product{industry.product_count === 1 ? "" : "s"}
                    </span>
                    <ArrowRight
                      aria-hidden="true"
                      className="size-4 -translate-x-1 opacity-0 transition-all group-hover:translate-x-0 group-hover:opacity-100"
                    />
                  </p>
                </Link>
              </li>
            ))}
          </ul>
        )}
      </div>
    </Section>
  );
}
