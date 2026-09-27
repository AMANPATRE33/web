import type { Metadata } from "next";
import Link from "next/link";
import { ArrowRight } from "lucide-react";

import { Breadcrumbs } from "@/components/catalog/primitives";
import { ProductGrid } from "@/components/catalog/ProductGrid";
import { SectionHeading } from "@/components/ui";
import { listCategories, listProducts } from "@/lib/api/catalog";


// Rendered per request. Prices, stock and availability must never be baked
// into a build: a stale static page would sell a variant that has since sold
// out, at a price the catalogue has since changed.
export const dynamic = "force-dynamic";

export const metadata: Metadata = {
  title: "5S workplace organisation signage",
  description:
    "The 5S collection: Seiri, Seiton, Seiso, Seiketsu and Shitsuke boards for workplace organisation. What each step means, how to implement it, and the boards that keep the standard visible.",
  alternates: { canonical: "/5s" },
};

/**
 * The 5S collection.
 *
 * The step definitions are the method itself, not product data, so they are
 * stated here. The product picks are the 5S category straight from the database -
 * resolved by category, so this page goes stale in the right way (a category
 * with no products renders an empty state) rather than showing products that no
 * longer exist.
 */
const STEPS = [
  {
    roman: "Seiri",
    name: "Sort",
    romaji: "整理",
    purpose: "Distinguish what is needed from what is not, and get the unneeded out of the area.",
    onFloor:
      "A red-tag system on everything in the area. A tag is a promise with a date on it, not a permanent label.",
    duration: "Day 1-2",
  },
  {
    roman: "Seiton",
    name: "Set in order",
    romaji: "整頓",
    purpose: "Give everything a fixed home so putting away takes seconds, not minutes.",
    onFloor:
      "Shadow boards and tool outlines. If a tool has no marked home, the area is not yet in Seiton.",
    duration: "Week 1",
  },
  {
    roman: "Seiso",
    name: "Shine",
    romaji: "清掃",
    purpose: "Clean while inspecting. Dirt marks a leak, a loose fitting or a bearing that is failing.",
    onFloor:
      "Scheduled cleaning as an inspection, not a cleaner's task. The person operating the machine does it.",
    duration: "Week 1-2",
  },
  {
    roman: "Seiketsu",
    name: "Standardise",
    romaji: "清潔",
    purpose: "Make the first three steps the default, so the standard survives a shift change.",
    onFloor:
      "Post the standard where the work happens, run visual checks on a fixed rhythm, and publish the results.",
    duration: "Week 2-4",
  },
  {
    roman: "Shitsuke",
    name: "Sustain",
    romaji: "躾",
    purpose: "Keep it. Audit, correct, repeat, and let the audit findings drive the next round.",
    onFloor:
      "Scheduled audits with visible results. An audit board nobody looks at is worse than none.",
    duration: "Ongoing",
  },
];

export default async function FiveSPage() {
  // Resolve the 5S category from the database rather than assuming a slug.
  const categories = await listCategories().catch(() => []);
  const fiveSCategory =
    categories.find((category) => category.slug === "5s-methodology") ??
    categories.find((category) => category.name.toLowerCase().includes("5s"));

  const products = fiveSCategory
    ? await listProducts({ category: [fiveSCategory.slug], per_page: 12, sort: "name_asc" })
        .then((page) => page.items)
        .catch(() => [])
    : [];

  const jsonLd = {
    "@context": "https://schema.org",
    "@type": "FAQPage",
    mainEntity: [
      {
        "@type": "Question",
        name: "What are the five S in 5S?",
        acceptedAnswer: {
          "@type": "Answer",
          text: "Seiri (Sort), Seiton (Set in order), Seiso (Shine), Seiketsu (Standardise) and Shitsuke (Sustain). They run in that order because each step depends on the one before it.",
        },
      },
      {
        "@type": "Question",
        name: "How long does a 5S implementation take?",
        acceptedAnswer: {
          "@type": "Answer",
          text: "A single workcell can reach Seiketsu in two to four weeks with a dedicated team. Shitsuke is not a phase with an end date - it is the ongoing audit rhythm that keeps the standard in place.",
        },
      },
      {
        "@type": "Question",
        name: "Why put 5S boards on the shop floor?",
        acceptedAnswer: {
          "@type": "Answer",
          text: "Because a standard in a manual is not a standard. Boards at the workstation make the target visible to the person doing the work, and they are what an auditor checks.",
        },
      },
    ],
  };

  return (
    <>
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: JSON.stringify(jsonLd) }}
      />

      {/* hero */}
      <section className="dark-surface border-b border-ink-200 bg-ink-950 text-white">
        <div className="container-page py-16 sm:py-20">
          <Breadcrumbs
            items={[{ name: "Home", href: "/" }, { name: "5S" }]}
            className="mb-6 [&_a]:text-ink-400 hover:[&_a]:text-white"
          />
          <p className="eyebrow !text-signal-400">Workplace organisation</p>
          <h1 className="mt-3 max-w-3xl text-[30px] leading-tight font-extrabold tracking-[-0.03em] sm:text-4xl lg:text-5xl">
            5S: a disciplined floor, five steps
          </h1>
          <p className="mt-5 max-w-2xl text-base leading-relaxed text-ink-300">
            5S is not a cleaning campaign. It is a sequence for making waste visible and then
            removing it, so problems surface while they are still cheap to fix. The order matters:
            each step is much harder without the one before it.
          </p>
          <ol className="mt-10 grid gap-px border border-white/10 bg-white/10 sm:grid-cols-5">
            {STEPS.map((step, index) => (
              <li key={step.roman} className="bg-ink-950 p-4">
                <p className="tabular font-mono text-[11px] text-signal-400">
                  {String(index + 1).padStart(2, "0")} &middot; {step.romaji}
                </p>
                <p className="mt-1.5 text-[15px] font-bold text-white">{step.roman}</p>
                <p className="text-[12px] text-ink-400">{step.name}</p>
              </li>
            ))}
          </ol>
        </div>
      </section>

      {/* steps in detail */}
      <section className="container-page py-14 sm:py-20">
        <SectionHeading
          eyebrow="The five steps"
          title="What each step actually involves"
          description="Generic 5S advice rarely survives contact with a real shop floor. This is what each step looks like when it is being run properly."
        />
        <ol className="space-y-5">
          {STEPS.map((step, index) => (
            <li
              key={step.roman}
              className="grid gap-5 border border-ink-200 bg-white p-5 sm:p-6 lg:grid-cols-[180px_1fr_1fr]"
            >
              <div>
                <p className="tabular font-mono text-[12px] text-ink-400">
                  {String(index + 1).padStart(2, "0")}
                </p>
                <p className="mt-1 text-[20px] font-bold text-ink-950">{step.roman}</p>
                <p className="text-[13px] font-medium text-ink-600">{step.name}</p>
                <p className="mt-1 font-mono text-[11px] text-ink-400">{step.romaji}</p>
                <p className="mt-3 inline-block rounded-xs bg-ink-100 px-2 py-0.5 text-[11px] font-semibold uppercase tracking-wide text-ink-600">
                  {step.duration}
                </p>
              </div>
              <div>
                <p className="eyebrow mb-1.5">Purpose</p>
                <p className="text-[14px] leading-relaxed text-ink-700">{step.purpose}</p>
              </div>
              <div>
                <p className="eyebrow mb-1.5">On the floor</p>
                <p className="text-[14px] leading-relaxed text-ink-700">{step.onFloor}</p>
              </div>
            </li>
          ))}
        </ol>
      </section>

      {/* products */}
      <section className="border-t border-ink-200 bg-ink-50 py-14 sm:py-20">
        <div className="container-page">
          <SectionHeading
            eyebrow="The collection"
            title="5S boards for the workstation"
            description="Post the standard where the work happens. Every board below is priced by material and size."
            action={
              fiveSCategory ? (
                <Link
                  href={`/category/${fiveSCategory.slug}`}
                  className="inline-flex items-center gap-1.5 text-sm font-semibold text-ink-900 underline underline-offset-4"
                >
                  All {fiveSCategory.product_count} in the category
                  <ArrowRight aria-hidden="true" className="size-4" />
                </Link>
              ) : null
            }
          />

          {products.length > 0 ? (
            <ProductGrid products={products} priorityCount={4} />
          ) : (
            <div className="border border-dashed border-ink-300 bg-white p-8 text-center">
              <p className="text-[15px] font-semibold text-ink-900">
                No 5S products are listed yet
              </p>
              <p className="mx-auto mt-2 max-w-md text-[14px] leading-relaxed text-ink-600">
                The 5S collection has not been assigned a category in the catalogue yet. Browse the
                full range in the meantime - most 5S boards sit under workplace and housekeeping
                signage.
              </p>
              <Link
                href="/shop"
                className="mt-5 inline-flex h-11 items-center justify-center rounded-xs border border-ink-950 bg-signal-400 px-5 text-sm font-semibold text-ink-950 hover:bg-signal-300"
              >
                Browse all products
              </Link>
            </div>
          )}
        </div>
      </section>

      {/* FAQ */}
      <section className="container-page py-14 sm:py-20">
        <SectionHeading eyebrow="Questions" title="Common 5S questions" />
        <dl className="space-y-5">
          {[
            [
              "What are the five S in 5S?",
              "Seiri (Sort), Seiton (Set in order), Seiso (Shine), Seiketsu (Standardise) and Shitsuke (Sustain). They run in that order because each step depends on the one before it.",
            ],
            [
              "How long does a 5S implementation take?",
              "A single workcell can reach Seiketsu in two to four weeks with a dedicated team. Shitsuke is not a phase with an end date - it is the ongoing audit rhythm that keeps the standard in place.",
            ],
            [
              "Why put 5S boards on the shop floor?",
              "Because a standard in a manual is not a standard. Boards at the workstation make the target visible to the person doing the work, and they are what an auditor checks.",
            ],
            [
              "Do 5S boards come in the same sizes as the rest of the range?",
              "Yes. Every 5S design uses the same nine standard sizes and four materials as the rest of the catalogue, so a 5S board matches the safety signage on the same wall.",
            ],
          ].map(([question, answer]) => (
            <div key={question} className="border-l-2 border-signal-400 pl-4">
              <dt className="text-[15px] font-semibold text-ink-950">{question}</dt>
              <dd className="mt-1.5 text-[14px] leading-relaxed text-ink-600">{answer}</dd>
            </div>
          ))}
        </dl>
      </section>
    </>
  );
}
