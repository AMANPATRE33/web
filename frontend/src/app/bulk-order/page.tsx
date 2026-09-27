import type { Metadata } from "next";

import { Breadcrumbs } from "@/components/catalog/primitives";
import { BulkOrderForm } from "@/components/bulk/BulkOrderForm";
import { Section } from "@/components/ui";
import { business } from "@/lib/env";

export const metadata: Metadata = {
  title: "Bulk order quotation",
  description:
    "Request a bulk quotation for safety posters, sign boards and workplace signage. Send your board list, sizes, materials and quantities and we will price freight properly.",
  alternates: { canonical: "/bulk-order" },
};

const STEPS = [
  {
    title: "Send your board list",
    body: "Names, sizes, materials and quantities. A rough list is fine — we will confirm the exact spec.",
  },
  {
    title: "We check what is actually printable",
    body: "Not every design is made in every size or material. We tell you what is available before quoting.",
  },
  {
    title: "You get a real quotation",
    body: "Unit prices, freight and any applicable GST, so the total is the total.",
  },
  {
    title: "Production and dispatch",
    body: "Approved orders go into production, then ship panelled and corner-guarded.",
  },
];

export default async function BulkOrderPage({
  searchParams,
}: {
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}) {
  const raw = await searchParams;
  const product = typeof raw.product === "string" ? raw.product : undefined;

  return (
    <Section className="pb-16">
      <div className="container-page">
        <Breadcrumbs
          items={[{ name: "Home", href: "/" }, { name: "Bulk order" }]}
          className="mb-4"
        />

        <div className="grid gap-10 lg:grid-cols-[1fr_360px] lg:items-start">
          <div>
            <header className="mb-8">
              <p className="eyebrow">B2B &amp; site-wide sets</p>
              <h1 className="mt-2 text-2xl sm:text-3xl">Request a bulk quotation</h1>
              <p className="mt-3 max-w-2xl text-[15px] leading-relaxed text-ink-600">
                For site-wide signage, facility rollouts or a project tender, a line-item price per
                board is the wrong tool. Send the list and we will price the whole job, freight
                included.
              </p>
            </header>

            {product ? (
              <p className="mb-6 border-l-2 border-signal-400 bg-ink-50 py-2.5 pl-4 text-[13px] text-ink-700">
                You came from a product page. Add it as the first line and add the rest below.
              </p>
            ) : null}

            <BulkOrderForm productSlug={product} />
          </div>

          <aside className="space-y-6 lg:sticky lg:top-32">
            <div className="border border-ink-200 bg-ink-50 p-5">
              <h2 className="text-[15px] font-bold text-ink-950">How it works</h2>
              <ol className="mt-4 space-y-4">
                {STEPS.map((step, index) => (
                  <li key={step.title} className="flex gap-3">
                    <span className="tabular flex size-6 shrink-0 items-center justify-center rounded-xs bg-ink-950 font-mono text-[11px] font-bold text-signal-400">
                      {index + 1}
                    </span>
                    <div>
                      <p className="text-[13px] font-semibold text-ink-950">{step.title}</p>
                      <p className="mt-0.5 text-[12px] leading-relaxed text-ink-600">
                        {step.body}
                      </p>
                    </div>
                  </li>
                ))}
              </ol>
            </div>

            <div className="border border-ink-200 p-5">
              <h2 className="text-[15px] font-bold text-ink-950">Talk to us directly</h2>
              <p className="mt-2 text-[13px] leading-relaxed text-ink-600">
                Faster than a form if you already know what you need.
              </p>
              <ul className="mt-4 space-y-2.5 text-[13px]">
                <li>
                  <a
                    href={business.whatsapp}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="font-semibold text-ink-950 underline underline-offset-4"
                  >
                    WhatsApp {business.phone}
                  </a>
                </li>
                <li>
                  <a
                    href={`mailto:${business.email}`}
                    className="font-semibold text-ink-950 underline underline-offset-4"
                  >
                    {business.email}
                  </a>
                </li>
                <li>
                  <a
                    href={business.phoneHref}
                    className="font-semibold text-ink-950 underline underline-offset-4"
                  >
                    {business.phone}
                  </a>
                </li>
              </ul>
            </div>
          </aside>
        </div>
      </div>
    </Section>
  );
}
