import type { Metadata } from "next";
import Link from "next/link";
import {
  CalendarClock,
  FileWarning,
  Layers,
  Mail,
  MapPin,
  Phone,
  Ruler,
  ShieldCheck,
  Truck,
} from "lucide-react";

import { Breadcrumbs } from "@/components/catalog/primitives";
import { Section } from "@/components/ui";
import { business, isPending } from "@/lib/env";

export const metadata: Metadata = {
  title: "About Safety Poster Prints",
  description:
    "Safety Poster Prints manufactures industrial safety posters and sign boards in Ankleshwar, Gujarat - MSDS and GHS boards, electrical safety, fire safety, 5S and workplace communication, delivered across India.",
  alternates: { canonical: "/about" },
};

/**
 * About.
 *
 * Every claim here is either verified business data from
 * `docs/REFERENCE_SITE_ANALYSIS.md` or a fact about how the business operates
 * that we can state plainly. Two things are deliberately absent: the year the
 * business was founded, and any customer count or testimonial. Neither is
 * published, so neither appears - not even hedged with an "approximately".
 */
export default function AboutPage() {
  return (
    <Section className="pb-16">
      <div className="container-page">
        <Breadcrumbs
          items={[{ name: "Home", href: "/" }, { name: "About" }]}
          className="mb-4"
        />

        <header className="mb-10 max-w-3xl">
          <p className="eyebrow">About us</p>
          <h1 className="mt-2 text-2xl sm:text-3xl">
            Safety signage, printed where it is needed
          </h1>
          <p className="mt-4 text-[17px] leading-relaxed text-ink-700">
            {business.name} prints industrial safety posters, sign boards and workplace
            communication products from {business.addressLocality}, {business.addressRegion}. The
            work is straightforward: take a hazard, decide the correct board, the correct material
            and the correct size, print it well, and ship it.
          </p>
        </header>

        <div className="grid gap-10 lg:grid-cols-[1fr_320px] lg:items-start">
          <div className="min-w-0 space-y-10">
            <section>
              <h2 className="text-lg">What we make</h2>
              <p className="mt-3 max-w-2xl text-[15px] leading-relaxed text-ink-600">
                The range covers hazard communication boards, mandatory and prohibition signage,
                emergency and fire action boards, MSDS and GHS chemical hazard signage, 5S
                workplace organisation boards, road and traffic signage, and general workplace
                communication. Most designs are available across nine standard sizes and four
                materials.
              </p>
              <div className="mt-6 grid gap-4 sm:grid-cols-2">
                <Fact
                  icon={<Ruler aria-hidden="true" />}
                  title="Nine standard sizes"
                  body="8x12, 12x18, 18x24, 24x36, 30x60, 36x48, 36x72, 48x72 and 48x96 inches. A set bought for one floor matches a set bought for the next."
                />
                <Fact
                  icon={<Layers aria-hidden="true" />}
                  title="Four materials"
                  body="3MM ACP, 5MM foam sheet, autoglow sticker and eco vinyl sticker. The right choice depends on where the board goes, not on which is cheapest."
                />
                <Fact
                  icon={<FileWarning aria-hidden="true" />}
                  title="Chemical safety"
                  body="MSDS display boards and GHS hazard pictograms, the signage a chemical store or dispensing point gets inspected on."
                />
                <Fact
                  icon={<Truck aria-hidden="true" />}
                  title="Packed to travel"
                  body="Boards ship panelled and corner-guarded, because a bent safety board is a safety board that cannot be read."
                />
              </div>
            </section>

            <section>
              <h2 className="text-lg">How ordering works</h2>
              <ol className="mt-4 space-y-4">
                {[
                  [
                    "Pick the board and the size",
                    "Every product page shows which materials and sizes are genuinely available for that design. Not all designs are made in all formats, and the site says so rather than letting you choose a combination that does not exist.",
                  ],
                  [
                    "Order a single board, or a site",
                    "Single boards and small quantities can be ordered directly. For a facility, a project or a tender, send the board list and we will quote it properly with freight included.",
                  ],
                  [
                    "We confirm before we charge",
                    "Volume pricing, applicable GST and shipping are confirmed on the quotation. The business GSTIN is not yet published; we will send ours on request.",
                  ],
                ].map(([title, body], index) => (
                  <li key={title} className="flex gap-4">
                    <span className="tabular flex size-7 shrink-0 items-center justify-center rounded-xs bg-ink-950 font-mono text-[12px] font-bold text-signal-400">
                      {index + 1}
                    </span>
                    <div>
                      <p className="text-[15px] font-semibold text-ink-950">{title}</p>
                      <p className="mt-1 text-[14px] leading-relaxed text-ink-600">{body}</p>
                    </div>
                  </li>
                ))}
              </ol>
            </section>

            <section>
              <h2 className="text-lg">Where we are</h2>
              <address className="mt-3 space-y-2.5 not-italic text-[15px] leading-relaxed text-ink-700">
                <p className="flex items-start gap-2.5">
                  <MapPin aria-hidden="true" className="mt-1 size-4 shrink-0 text-ink-400" />
                  <span>{business.address}</span>
                </p>
                <p className="flex items-center gap-2.5">
                  <Phone aria-hidden="true" className="size-4 shrink-0 text-ink-400" />
                  <a href={business.phoneHref} className="hover:underline">
                    {business.phone}
                  </a>
                </p>
                <p className="flex items-center gap-2.5">
                  <Mail aria-hidden="true" className="size-4 shrink-0 text-ink-400" />
                  <a href={`mailto:${business.email}`} className="hover:underline">
                    {business.email}
                  </a>
                </p>
                <p className="flex items-center gap-2.5">
                  <CalendarClock aria-hidden="true" className="size-4 shrink-0 text-ink-400" />
                  {isPending(business.businessHours) ? (
                    <span className="italic text-ink-500">
                      Business hours have not been published yet. Call or email and we will
                      confirm them.
                    </span>
                  ) : (
                    <span>{business.businessHours}</span>
                  )}
                </p>
              </address>
            </section>
          </div>

          <aside className="space-y-4 lg:sticky lg:top-32">
            <div className="border border-ink-200 bg-ink-50 p-5">
              <h2 className="flex items-center gap-2 text-[15px] font-bold text-ink-950">
                <ShieldCheck aria-hidden="true" className="size-4 text-signal-500" />
                Talk to us
              </h2>
              <p className="mt-2 text-[13px] leading-relaxed text-ink-600">
                If you are not sure which board or material a site needs, ask. It is faster than
                ordering the wrong thing.
              </p>
              <Link
                href="/contact"
                className="mt-4 inline-flex h-10 w-full items-center justify-center rounded-xs border border-ink-950 bg-signal-400 px-4 text-[13px] font-bold text-ink-950 transition-colors hover:bg-signal-300"
              >
                Contact us
              </Link>
            </div>

            <div className="border border-ink-200 p-5">
              <h2 className="text-[15px] font-bold text-ink-950">Browse first</h2>
              <ul className="mt-3 space-y-1.5 text-[13px]">
                {[
                  { href: "/shop", label: "All products" },
                  { href: "/category", label: "All categories" },
                  { href: "/industries", label: "By industry" },
                  { href: "/msds", label: "MSDS & GHS boards" },
                  { href: "/5s", label: "5S methodology" },
                  { href: "/blog", label: "Guides" },
                ].map((link) => (
                  <li key={link.href}>
                    <Link
                      href={link.href}
                      className="text-ink-700 hover:text-ink-950 hover:underline"
                    >
                      {link.label}
                    </Link>
                  </li>
                ))}
              </ul>
            </div>
          </aside>
        </div>
      </div>
    </Section>
  );
}

function Fact({
  icon,
  title,
  body,
}: {
  icon: React.ReactNode;
  title: string;
  body: string;
}) {
  return (
    <div className="border border-ink-200 p-4">
      <p className="flex items-center gap-2.5 text-ink-500">
        <span className="[&_svg]:size-[18px]">{icon}</span>
        <span className="text-[14px] font-semibold text-ink-950">{title}</span>
      </p>
      <p className="mt-2 text-[13px] leading-relaxed text-ink-600">{body}</p>
    </div>
  );
}
