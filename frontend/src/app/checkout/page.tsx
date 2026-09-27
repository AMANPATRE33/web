import type { Metadata } from "next";
import Link from "next/link";

import { Breadcrumbs } from "@/components/catalog/primitives";
import { CartView } from "@/components/cart/CartView";
import { Button, Section } from "@/components/ui";
import { business } from "@/lib/env";

export const metadata: Metadata = {
  title: "Checkout",
  description: "Complete your safety signage order.",
  robots: { index: false, follow: false },
};

export default function CheckoutPage() {
  return (
    <Section className="pb-16">
      <div className="container-page">
        <Breadcrumbs
          items={[
            { name: "Home", href: "/" },
            { name: "Cart", href: "/cart" },
            { name: "Checkout" },
          ]}
          className="mb-4"
        />

        <header className="mb-8">
          <h1 className="text-2xl sm:text-3xl">Checkout</h1>
          <p className="mt-2 max-w-2xl text-[15px] text-ink-600">
            Review what you are ordering. The address, payment and order-placement steps come next,
            once the order and payment pipeline is built.
          </p>
        </header>

        <div className="grid gap-8 lg:grid-cols-[1fr_320px] lg:items-start">
          <div className="min-w-0">
            <CartView compact />

            <div className="mt-8 border border-dashed border-ink-300 bg-ink-50 p-6">
              <p className="text-[15px] font-semibold text-ink-950">
                Checkout is not connected yet
              </p>
              <p className="mt-2 max-w-2xl text-[14px] leading-relaxed text-ink-600">
                The order, inventory reservation and Razorpay payment pipeline is a later build
                phase. Your cart is safe and still here, but there is no payment step and pressing
                through would not create an order.
              </p>
              <p className="mt-3 max-w-2xl text-[14px] leading-relaxed text-ink-600">
                To order now, contact us directly and we will take the order by phone or WhatsApp.
              </p>
              <div className="mt-5 flex flex-wrap gap-2">
                <Button variant="primary" asChild>
                  <a href={business.whatsapp} target="_blank" rel="noopener noreferrer">
                    WhatsApp {business.phone}
                  </a>
                </Button>
                <Button variant="outline" asChild>
                  <a href={business.phoneHref}>Call {business.phone}</a>
                </Button>
                <Button variant="outline" asChild>
                  <Link href="/bulk-order">Request a bulk quote</Link>
                </Button>
              </div>
            </div>
          </div>

          <aside className="space-y-4 lg:sticky lg:top-32">
            <div className="border border-ink-200 bg-ink-50 p-5">
              <h2 className="text-[15px] font-bold text-ink-950">What happens next</h2>
              <ol className="mt-3 space-y-2.5 text-[13px] leading-relaxed text-ink-600">
                {[
                  "Delivery address and GSTIN, if you need a business invoice.",
                  "Shipping and GST applied server-side and confirmed to you.",
                  "Payment, then stock is reserved against your order.",
                  "Production, packing and dispatch with the invoice attached.",
                ].map((step, index) => (
                  <li key={step} className="flex gap-2.5">
                    <span className="tabular flex size-5 shrink-0 items-center justify-center rounded-xs bg-ink-950 font-mono text-[10px] font-bold text-signal-400">
                      {index + 1}
                    </span>
                    {step}
                  </li>
                ))}
              </ol>
            </div>

            <div className="border border-ink-200 p-5">
              <h2 className="text-[15px] font-bold text-ink-950">Business orders</h2>
              <p className="mt-2 text-[13px] leading-relaxed text-ink-600">
                For site-wide quantities, a quotation with freight included is faster and cheaper
                than checkout.
              </p>
              <Link
                href="/bulk-order"
                className="mt-4 inline-flex h-10 w-full items-center justify-center rounded-xs border border-ink-950 bg-signal-400 px-4 text-[13px] font-bold text-ink-950 transition-colors hover:bg-signal-300"
              >
                Request a bulk quote
              </Link>
            </div>
          </aside>
        </div>
      </div>
    </Section>
  );
}
