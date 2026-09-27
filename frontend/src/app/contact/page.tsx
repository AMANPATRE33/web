import type { Metadata } from "next";
import Link from "next/link";

import { Breadcrumbs } from "@/components/catalog/primitives";
import { Button, Input, Label, Section, Textarea } from "@/components/ui";
import { business, isPending } from "@/lib/env";

export const metadata: Metadata = {
  title: "Contact us",
  description: `Contact Safety Poster Prints. ${business.address}. Phone ${business.phone}, email ${business.email}.`,
  alternates: { canonical: "/contact" },
};

export default function ContactPage() {
  return (
    <Section className="pb-16">
      <div className="container-page">
        <Breadcrumbs
          items={[{ name: "Home", href: "/" }, { name: "Contact" }]}
          className="mb-4"
        />

        <div className="grid gap-10 lg:grid-cols-[1fr_360px] lg:items-start">
          <div className="min-w-0">
            <header className="mb-8">
              <p className="eyebrow">Get in touch</p>
              <h1 className="mt-2 text-2xl sm:text-3xl">Contact us</h1>
              <p className="mt-3 max-w-2xl text-[15px] leading-relaxed text-ink-600">
                For a quick question, WhatsApp or a phone call is usually fastest. For a quotation,
                use the bulk order form and send the whole board list at once.
              </p>
            </header>

            <div className="border-l-2 border-signal-400 bg-ink-50 p-5">
              <p className="text-[14px] font-semibold text-ink-950">
                The contact form is not live yet
              </p>
              <p className="mt-2 max-w-2xl text-[14px] leading-relaxed text-ink-600">
                The messages API is a later build phase, so nothing submitted here would reach us.
                Rather than let a message disappear, use one of the channels below &mdash; all three
                are answered.
              </p>
              <ul className="mt-4 space-y-1.5 text-[14px] text-ink-800">
                <li>
                  <a
                    href={business.whatsapp}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="font-semibold text-ink-950 underline underline-offset-4"
                  >
                    WhatsApp {business.phone}
                  </a>{" "}
                  &mdash; quickest
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

            {/*
              The form is rendered but inert. Showing a working-looking form that
              silently discards input is worse than showing none, so every control
              is disabled and the reason is stated above.
            */}
            <fieldset disabled className="mt-10 opacity-70">
              <legend className="text-[15px] font-bold text-ink-950">
                Contact form (not yet enabled)
              </legend>
              <div className="mt-4 grid gap-4 sm:grid-cols-2">
                <div>
                  <Label htmlFor="contact-name" className="mb-1.5">
                    Your name
                  </Label>
                  <Input id="contact-name" placeholder="Full name" />
                </div>
                <div>
                  <Label htmlFor="contact-company" className="mb-1.5">
                    Company
                  </Label>
                  <Input id="contact-company" placeholder="Company name" />
                </div>
                <div>
                  <Label htmlFor="contact-email" className="mb-1.5">
                    Email
                  </Label>
                  <Input id="contact-email" type="email" placeholder="you@company.com" />
                </div>
                <div>
                  <Label htmlFor="contact-phone" className="mb-1.5">
                    Phone
                  </Label>
                  <Input id="contact-phone" type="tel" placeholder="+91" />
                </div>
                <div className="sm:col-span-2">
                  <Label htmlFor="contact-message" className="mb-1.5">
                    Message
                  </Label>
                  <Textarea
                    id="contact-message"
                    rows={5}
                    placeholder="What do you need? Include sizes, materials and quantities if you know them."
                  />
                </div>
              </div>
              <Button variant="primary" className="mt-5" disabled>
                Send message
              </Button>
            </fieldset>
          </div>

          <aside className="space-y-4 lg:sticky lg:top-32">
            <div className="border border-ink-200 bg-ink-50 p-5">
              <h2 className="text-[15px] font-bold text-ink-950">Business</h2>
              <address className="mt-3 space-y-2.5 not-italic text-[13px] leading-relaxed text-ink-700">
                <p>{business.address}</p>
                <p>
                  <a href={business.phoneHref} className="font-semibold hover:underline">
                    {business.phone}
                  </a>
                </p>
                <p>
                  <a
                    href={`mailto:${business.email}`}
                    className="font-semibold hover:underline"
                  >
                    {business.email}
                  </a>
                </p>
                <p>
                  <a
                    href={business.instagram}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="font-semibold hover:underline"
                  >
                    Instagram
                  </a>
                </p>
              </address>

              <dl className="mt-5 space-y-2 border-t border-ink-300 pt-4 text-[12px]">
                <div className="flex justify-between gap-3">
                  <dt className="text-ink-500">Business hours</dt>
                  <dd className={isPending(business.businessHours) ? "italic text-ink-400" : "text-ink-700"}>
                    {isPending(business.businessHours) ? "Not published" : business.businessHours}
                  </dd>
                </div>
                <div className="flex justify-between gap-3">
                  <dt className="text-ink-500">GSTIN</dt>
                  <dd className={isPending(business.gstin) ? "italic text-ink-400" : "font-mono text-ink-700"}>
                    {isPending(business.gstin) ? "Not published" : business.gstin}
                  </dd>
                </div>
                <div className="flex justify-between gap-3">
                  <dt className="text-ink-500">Map</dt>
                  <dd className={isPending(business.mapsUrl) ? "italic text-ink-400" : "text-ink-700"}>
                    {isPending(business.mapsUrl) ? "Not linked yet" : "Available"}
                  </dd>
                </div>
              </dl>
            </div>

            <div className="border border-ink-200 p-5">
              <h2 className="text-[15px] font-bold text-ink-950">Ordering in bulk?</h2>
              <p className="mt-2 text-[13px] leading-relaxed text-ink-600">
                The bulk order form collects a full board list with sizes, materials and
                quantities, which is what we need to price a site properly.
              </p>
              <Link
                href="/bulk-order"
                className="mt-4 inline-flex h-10 w-full items-center justify-center rounded-xs border border-ink-950 bg-signal-400 px-4 text-[13px] font-bold text-ink-950 transition-colors hover:bg-signal-300"
              >
                Go to bulk order
              </Link>
            </div>
          </aside>
        </div>
      </div>
    </Section>
  );
}
