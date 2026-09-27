import type { Metadata } from "next";
import Link from "next/link";
import { ArrowRight } from "lucide-react";

import { Breadcrumbs } from "@/components/catalog/primitives";
import { ProductGrid } from "@/components/catalog/ProductGrid";
import { SectionHeading } from "@/components/ui";
import { getCategory, listProducts } from "@/lib/api/catalog";
import { ApiError } from "@/lib/api/client";
import { business } from "@/lib/env";

// Rendered per request. Prices, stock and availability must never be baked
// into a build: a stale static page would sell a variant that has since sold
// out, at a price the catalogue has since changed.
export const dynamic = "force-dynamic";

export const metadata: Metadata = {
  title: "MSDS and GHS chemical hazard boards",
  description:
    "MSDS display boards and GHS hazard pictogram signage for chemical stores, laboratories and dispensing points. Available in ACP, foam sheet, vinyl and autoglow, in nine standard sizes.",
  alternates: { canonical: "/msds" },
};

/**
 * MSDS collection.
 *
 * A dedicated landing page for the `msds` category rather than a redirect to it,
 * because MSDS is the single most searched term in this catalogue and a buyer
 * arriving on it needs the pictogram and material guidance, not just a grid.
 *
 * The `msds` category is the second most requested on the live site (52 of 152
 * products). That count is a fact about the source site, not about this
 * database, and the product numbers on this page are read from the API instead.
 */
const GHS_PICTOGRAMS = [
  { name: "Explosive", hint: "Exploding bomb" },
  { name: "Flammable", hint: "Flame" },
  { name: "Oxidising", hint: "Flame over circle" },
  { name: "Compressed gas", hint: "Gas cylinder" },
  { name: "Corrosive", hint: "Test tubes on a hand and surface" },
  { name: "Acute toxicity", hint: "Skull and crossbones" },
  { name: "Health hazard", hint: "Person with a star-shaped chest" },
  { name: "Irritant", hint: "Exclamation mark" },
  { name: "Environmental", hint: "Dead tree and fish" },
];

export default async function MsdsPage() {
  // Resolved by slug from the database. If MSDS is not a category, the page
  // degrades to an explanatory empty state rather than a 404 - the content is
  // still useful and the URL may already be linked from elsewhere.
  const category = await getCategory("msds").catch((error: unknown) => {
    if (error instanceof ApiError && error.isNotFound) return null;
    throw error;
  });

  const products = category
    ? await listProducts({ category: [category.slug], per_page: 24, sort: "price_asc" })
        .then((page) => page.items)
        .catch(() => [])
    : [];

  const total = category?.product_count ?? 0;

  return (
    <>
      {/* hero */}
      <section className="dark-surface border-b border-ink-200 bg-ink-950 text-white">
        <div className="container-page py-16 sm:py-20">
          <Breadcrumbs
            items={[{ name: "Home", href: "/" }, { name: "MSDS" }]}
            className="mb-6 [&_a]:text-ink-400 hover:[&_a]:text-white"
          />
          <p className="eyebrow !text-signal-400">Chemical safety</p>
          <h1 className="mt-3 max-w-3xl text-[30px] leading-tight font-extrabold tracking-[-0.03em] sm:text-4xl lg:text-5xl">
            MSDS and GHS hazard boards
          </h1>
          <p className="mt-5 max-w-2xl text-base leading-relaxed text-ink-300">
            Chemical stores, dispensing points and laboratories get inspected on whether the hazard
            information is visible and current. These are the boards that satisfy that, in the
            materials that survive the environment they go in.
          </p>
          {total > 0 ? (
            <p className="mt-6 inline-block rounded-xs border border-white/15 px-3 py-1.5 text-[13px] font-semibold text-white">
              {total} MSDS and chemical hazard product{total === 1 ? "" : "s"}
            </p>
          ) : null}
        </div>
      </section>

      {/* pictogram reference */}
      <section className="container-page py-14 sm:py-16">
        <SectionHeading
          eyebrow="Reference"
          title="GHS pictograms"
          description="Nine pictograms in the Globally Harmonised System. A chemical area normally needs the hazard classes actually present, not all nine."
        />
        <ul className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {GHS_PICTOGRAMS.map((pictogram) => (
            <li
              key={pictogram.name}
              className="flex items-center gap-3.5 border border-ink-200 bg-white p-4"
            >
              {/* A neutral placeholder mark, not a reproduction of the GHS
                  diamond. The official pictogram artwork is not licensed for
                  redrawing here, and an inaccurate diamond on a safety page
                  would be genuinely dangerous. */}
              <span
                aria-hidden="true"
                className="flex size-11 shrink-0 items-center justify-center border-2 border-ink-300 text-[10px] font-bold uppercase text-ink-400"
              >
                GHS
              </span>
              <span className="min-w-0">
                <span className="block text-[14px] font-semibold text-ink-950">
                  {pictogram.name}
                </span>
                <span className="block text-[12px] text-ink-500">{pictogram.hint}</span>
              </span>
            </li>
          ))}
        </ul>
        <p className="mt-4 text-[12px] leading-relaxed text-ink-500">
          Pictogram artwork and hazard statements come from your own chemical inventory
          documentation. Ask us for the board formats and we will print to your specification.
        </p>
      </section>

      {/* material guidance */}
      <section className="border-y border-ink-200 bg-ink-50 py-14 sm:py-16">
        <div className="container-page">
          <SectionHeading
            eyebrow="Choosing a material"
            title="Where the board goes decides the material"
            description="This is the question we are asked most about MSDS boards, and the answer is almost always the environment rather than the budget."
          />
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            {[
              {
                material: "3MM ACP",
                where: "Indoor stores, labs, offices",
                note: "Rigid and flat. The default for a wall-mounted indoor board where moisture is not a factor.",
              },
              {
                material: "5MM FOAMSHEET",
                where: "Workshops, racks, light outdoor use",
                note: "Lighter than ACP and easy to fix with adhesive or fasteners. Handles a slightly damp environment better.",
              },
              {
                material: "ECO VINYL STICKER",
                where: "Drums, tanks, cylinders, pipework",
                note: "Conforms to a curved surface. The right choice when the signage goes on a container rather than a wall.",
              },
              {
                material: "AUTOGLOW STICKER",
                where: "Unlit areas, exits, emergency routes",
                note: "Phosphorescent. Charges under normal light and stays readable in a power cut or smoke-filled corridor.",
              },
            ].map((entry) => (
              <div key={entry.material} className="border border-ink-200 bg-white p-4">
                <p className="font-mono text-[12px] font-semibold uppercase tracking-wide text-ink-950">
                  {entry.material}
                </p>
                <p className="mt-1.5 text-[12px] font-medium text-signal-600">{entry.where}</p>
                <p className="mt-2 text-[13px] leading-relaxed text-ink-600">{entry.note}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* products */}
      <section className="container-page py-14 sm:py-20">
        <SectionHeading
          eyebrow="The collection"
          title="MSDS and chemical hazard boards"
          description="Sorted by price so the small formats are visible first. Every board is available in the sizes and materials we actually produce."
          action={
            category ? (
              <Link
                href={`/category/${category.slug}`}
                className="inline-flex items-center gap-1.5 text-sm font-semibold text-ink-900 underline underline-offset-4"
              >
                Filter by size and material
                <ArrowRight aria-hidden="true" className="size-4" />
              </Link>
            ) : null
          }
        />

        {products.length > 0 ? (
          <>
            <ProductGrid products={products} priorityCount={4} />
            {products.length >= 24 ? (
              <div className="mt-10 text-center">
                <Link
                  href={`/category/${category!.slug}`}
                  className="inline-flex h-12 items-center justify-center rounded-xs border border-ink-900 bg-white px-6 text-sm font-semibold text-ink-900 hover:bg-ink-50"
                >
                  See all {total} products
                </Link>
              </div>
            ) : null}
          </>
        ) : (
          <div className="border border-dashed border-ink-300 bg-ink-50 p-8 text-center">
            <p className="text-[15px] font-semibold text-ink-900">
              The MSDS category is not populated yet
            </p>
            <p className="mx-auto mt-2 max-w-md text-[14px] leading-relaxed text-ink-600">
              There is no <code className="font-mono">msds</code> category in the catalogue at the
              moment. Browse the full range, or send us your board list and we will print to spec.
            </p>
            <div className="mt-5 flex flex-wrap justify-center gap-2">
              <Link
                href="/shop"
                className="inline-flex h-11 items-center justify-center rounded-xs border border-ink-950 bg-signal-400 px-5 text-sm font-semibold text-ink-950 hover:bg-signal-300"
              >
                Browse all products
              </Link>
              <a
                href={business.whatsapp}
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex h-11 items-center justify-center rounded-xs border border-ink-900 bg-white px-5 text-sm font-semibold text-ink-900 hover:bg-ink-50"
              >
                Ask for a custom board
              </a>
            </div>
          </div>
        )}
      </section>
    </>
  );
}
