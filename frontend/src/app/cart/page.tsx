import type { Metadata } from "next";

import { Breadcrumbs } from "@/components/catalog/primitives";
import { CartView } from "@/components/cart/CartView";
import { Section } from "@/components/ui";

export const metadata: Metadata = {
  title: "Your cart",
  description: "Review the safety signage in your cart before checkout.",
  robots: { index: false, follow: true },
};

export default function CartPage() {
  return (
    <Section className="pb-16">
      <div className="container-page">
        <Breadcrumbs
          items={[{ name: "Home", href: "/" }, { name: "Cart" }]}
          className="mb-4"
        />
        <header className="mb-8">
          <h1 className="text-2xl sm:text-3xl">Your cart</h1>
          <p className="mt-2 max-w-2xl text-[15px] text-ink-600">
            Each line is a specific material and size. Two lines of the same board in different
            materials stay separate, because that is how they are manufactured and priced.
          </p>
        </header>
        <CartView />
      </div>
    </Section>
  );
}
