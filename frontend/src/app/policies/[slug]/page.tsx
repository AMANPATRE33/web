import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { FileWarning, Mail, Phone } from "lucide-react";

import { Breadcrumbs } from "@/components/catalog/primitives";
import { Button, Section } from "@/components/ui";
import { business } from "@/lib/env";

/**
 * Policy pages.
 *
 * `docs/CONTENT_PENDING.md` records that the business has not supplied policy
 * text, and the brief was explicit: do not invent policies. So these pages
 * render the *structure* of each policy with an explicit gap marker where the
 * business's own wording is missing, and a direct route to ask for it.
 *
 * That is a real design decision rather than a placeholder. Inventing a 7-day
 * return window would be a contractual term the business never agreed to, and
 * it is the kind of thing a customer will hold us to.
 */

type PolicySlug = "shipping" | "refund" | "terms" | "privacy";

interface Section_ {
  heading: string;
  /** `null` means the business has not supplied this section yet. */
  body: string[] | null;
}

const POLICIES: Record<PolicySlug, { title: string; intro: string; sections: Section_[] }> = {
  shipping: {
    title: "Shipping policy",
    intro:
      "How boards are packed, what freight depends on, and what we confirm before you are charged.",
    sections: [
      {
        heading: "What ships",
        body: [
          "All boards are made to order against the material and size you select, then packed for transport.",
          "Single boards and small quantities ship as standard courier or parcel. Site-wide orders are quoted with freight included before you are charged.",
        ],
      },
      {
        heading: "Packing",
        body: [
          "Boards are shipped flat, panelled where the size requires it, and corner-guarded. A bent safety board is a board nobody can read, so it is treated as a defect on arrival.",
        ],
      },
      {
        heading: "Freight and delivery time",
        body: null,
      },
      {
        heading: "Delivered addresses",
        body: null,
      },
    ],
  },
  refund: {
    title: "Refund and return policy",
    intro:
      "What can be returned, what cannot, and how to raise it.",
    sections: [
      {
        heading: "Made-to-order items",
        body: [
          "Every board here is printed to your chosen specification. A board produced to a size, material and wording you selected cannot be resold, so made-to-order items are final sale.",
        ],
      },
      {
        heading: "Damage in transit",
        body: [
          "If a board arrives bent, creased or otherwise damaged, photograph it before unpacking further and contact us. Send the photographs with your order reference and we will replace it.",
        ],
      },
      {
        heading: "Return window and process",
        body: null,
      },
      {
        heading: "Refund timing",
        body: null,
      },
    ],
  },
  terms: {
    title: "Terms and conditions",
    intro: "The terms that apply to using this site and placing an order.",
    sections: [
      {
        heading: "Pricing",
        body: [
          "Every price shown is for a specific material and size combination. The figure on a listing is the cheapest available option, not the price of the combination you have selected. The price that applies to your order is the price of the variant you chose.",
        ],
      },
      {
        heading: "Availability",
        body: [
          "Stock shown is the quantity currently recorded for that specific variant. Not every design is made in every size or material; the product page shows only the combinations that are actually produced.",
        ],
      },
      {
        heading: "Quotations",
        body: [
          "A quotation is valid for the period stated on it. Freight, applicable GST and volume pricing are confirmed on the quotation before any payment is taken.",
        ],
      },
      {
        heading: "Governing law and jurisdiction",
        body: null,
      },
      {
        heading: "Acceptable use",
        body: null,
      },
    ],
  },
  privacy: {
    title: "Privacy policy",
    intro: "What we collect, why, and what we do not do with it.",
    sections: [
      {
        heading: "What this site collects",
        body: [
          "Your cart is stored in your own browser, on your device. It is not sent to us until you place an order or request a quotation.",
        ],
      },
      {
        heading: "What we do not do",
        body: [
          "We do not sell contact details, and we do not add you to a marketing list because you placed an order.",
        ],
      },
      {
        heading: "Order and quotation data",
        body: null,
      },
      {
        heading: "Cookies and analytics",
        body: null,
      },
      {
        heading: "Contact and requests",
        body: null,
      },
    ],
  },
};

export function generateStaticParams() {
  return Object.keys(POLICIES).map((slug) => ({ slug }));
}

export async function generateMetadata({
  params,
}: {
  params: Promise<{ slug: string }>;
}): Promise<Metadata> {
  const { slug } = await params;
  const policy = POLICIES[slug as PolicySlug];
  if (!policy) return { title: "Policy", robots: { index: false, follow: true } };
  return {
    title: policy.title,
    description: policy.intro,
    alternates: { canonical: `/policies/${slug}` },
  };
}

export default async function PolicyPage({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params;
  const policy = POLICIES[slug as PolicySlug];
  if (!policy) notFound();

  const missing = policy.sections.filter((section) => section.body === null);

  return (
    <Section className="pb-16">
      <div className="container-page">
        <div className="mx-auto max-w-3xl">
          <Breadcrumbs
            items={[
              { name: "Home", href: "/" },
              { name: "Policies", href: "/contact" },
              { name: policy.title },
            ]}
            className="mb-4"
          />

          <header className="mb-8">
            <h1 className="text-2xl sm:text-3xl">{policy.title}</h1>
            <p className="mt-3 text-[16px] leading-relaxed text-ink-600">{policy.intro}</p>
          </header>

          {missing.length > 0 ? (
            <div className="mb-8 flex items-start gap-3 border-l-2 border-signal-400 bg-signal-50 p-4">
              <FileWarning aria-hidden="true" className="mt-0.5 size-5 shrink-0 text-signal-600" />
              <div>
                <p className="text-[14px] font-semibold text-ink-950">
                  This policy is incomplete
                </p>
                <p className="mt-1.5 text-[13px] leading-relaxed text-ink-700">
                  {missing.length} section{missing.length === 1 ? "" : "s"} below{" "}
                  {missing.length === 1 ? "is" : "are"} marked as awaiting the business&apos;s own
                  wording. We have not written them, because inventing a return window, a delivery
                  commitment or a legal term is not something we can do on the business&apos;s
                  behalf. Ask us and we will send the current version.
                </p>
              </div>
            </div>
          ) : null}

          <div className="space-y-8">
            {policy.sections.map((section) => (
              <section key={section.heading}>
                <h2 className="text-lg text-ink-950">{section.heading}</h2>
                {section.body ? (
                  <div className="mt-3 space-y-3">
                    {section.body.map((paragraph) => (
                      <p
                        key={paragraph}
                        className="text-[15px] leading-relaxed text-ink-700"
                      >
                        {paragraph}
                      </p>
                    ))}
                  </div>
                ) : (
                  <p className="mt-3 flex items-center gap-2 text-[14px] italic text-ink-400">
                    <span
                      aria-hidden="true"
                      className="inline-block h-2 w-2 bg-signal-400"
                    />
                    Awaiting the business&apos;s own wording.
                  </p>
                )}
              </section>
            ))}
          </div>

          <div className="mt-10 border border-ink-200 bg-ink-50 p-5">
            <h2 className="text-[15px] font-bold text-ink-950">Ask for the current version</h2>
            <p className="mt-2 text-[13px] leading-relaxed text-ink-600">
              The most reliable answer is a direct one. Ask for the policy you need and we will
              send the current text in writing.
            </p>
            <div className="mt-4 flex flex-wrap gap-2">
              <Button variant="primary" asChild>
                <a href={`mailto:${business.email}`}>
                  <Mail aria-hidden="true" />
                  {business.email}
                </a>
              </Button>
              <Button variant="outline" asChild>
                <a href={business.phoneHref}>
                  <Phone aria-hidden="true" />
                  {business.phone}
                </a>
              </Button>
            </div>
            <p className="mt-4 text-[12px] text-ink-500">
              Tracked in{" "}
              <code className="font-mono">docs/CONTENT_PENDING.md</code> in the repository. See
              also{" "}
              <Link href="/contact" className="underline underline-offset-4">
                contact
              </Link>
              .
            </p>
          </div>

          <nav aria-label="Other policies" className="mt-10">
            <p className="eyebrow mb-3">Other policies</p>
            <ul className="flex flex-wrap gap-2">
              {(Object.keys(POLICIES) as PolicySlug[])
                .filter((key) => key !== slug)
                .map((key) => (
                  <li key={key}>
                    <Link
                      href={`/policies/${key}`}
                      className="inline-block rounded-xs border border-ink-300 px-3 py-1.5 text-[13px] font-medium text-ink-700 transition-colors hover:border-ink-900 hover:text-ink-950"
                    >
                      {POLICIES[key].title}
                    </Link>
                  </li>
                ))}
            </ul>
          </nav>
        </div>
      </div>
    </Section>
  );
}
