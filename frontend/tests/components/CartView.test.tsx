import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useEffect } from "react";
import { describe, expect, it, vi } from "vitest";

import { CartView } from "@/components/cart/CartView";
import { CartProvider, useCart } from "@/components/cart/CartProvider";
import type { Money } from "@/lib/api/types";

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn(), replace: vi.fn(), refresh: vi.fn() }),
  usePathname: () => "/cart",
  useSearchParams: () => new URLSearchParams(),
}));

vi.mock("next/link", () => ({
  default: ({
    children,
    href,
    ...rest
  }: React.AnchorHTMLAttributes<HTMLAnchorElement> & { href: string }) => (
    <a href={href} {...rest}>
      {children}
    </a>
  ),
}));

function money(amount: number): Money {
  const rupees = Math.floor(amount / 100);
  return {
    amount,
    currency: "INR",
    symbol: "Rs.",
    formatted: `Rs.${rupees.toLocaleString("en-IN")}`,
  };
}

const LINE = {
  variantId: "v-acp-1824",
  productId: "p1",
  productSlug: "danger-high-voltage",
  productTitle: "Danger High Voltage",
  variantSku: "SPP-ELS-001-ACP-18X24",
  material: "3MM ACP",
  size: "18x24",
  imageUrl: "/seed/electrical-safety/a.svg",
  unitPrice: money(18_000),
  maxQuantity: 50,
};

/**
 * Seeds the cart on mount, so every test starts from a known state without an
 * extra click. `useSyncExternalStore` notifies synchronously on write, so the
 * `CartView` below re-renders with the seeded lines immediately.
 */
function Seed({ lines }: { lines: Array<typeof LINE & { quantity: number }> }) {
  const { addLine } = useCart();
  useEffect(() => {
    lines.forEach((line) => addLine(line));
    // Seed once on mount: re-running would double the quantities.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);
  return <CartView />;
}

function renderCart(lines: Array<typeof LINE & { quantity: number }> = []) {
  return render(
    <CartProvider>
      <Seed lines={lines} />
    </CartProvider>,
  );
}

describe("CartView - empty state", () => {
  it("never renders a blank screen", () => {
    renderCart([]);
    expect(screen.getByText("Your cart is empty")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Shop all products/ })).toBeInTheDocument();
  });
});

describe("CartView - line identity", () => {
  it("keeps two variants of the same product as separate lines", async () => {
    renderCart([
      { ...LINE, quantity: 1 },
      { ...LINE, variantId: "v-vinyl-1824", material: "ECO VINYL STICKER", variantSku: "SPP-ELS-001-VIN-18X24", unitPrice: money(6_000), quantity: 1 },
    ]);

    const items = screen.getAllByRole("listitem");
    expect(items.length).toBeGreaterThanOrEqual(2);
    expect(screen.getByText("3MM ACP")).toBeInTheDocument();
    expect(screen.getByText("ECO VINYL STICKER")).toBeInTheDocument();
  });

  it("shows the material and size on every line, not just the product name", () => {
    renderCart([{ ...LINE, quantity: 1 }]);
    // Identity is variant-level, so the customer must be able to see it.
    expect(screen.getByText("3MM ACP")).toBeInTheDocument();
    expect(screen.getByText("18x24 in.")).toBeInTheDocument();
    expect(screen.getByText("SPP-ELS-001-ACP-18X24")).toBeInTheDocument();
  });
});

describe("CartView - quantity controls", () => {
  it("increments and decrements a line", async () => {
    const user = userEvent.setup();
    renderCart([{ ...LINE, quantity: 1 }]);

    await user.click(
      screen.getByRole("button", { name: "Increase quantity of Danger High Voltage" }),
    );
    expect(screen.getByText("2")).toBeInTheDocument();

    await user.click(
      screen.getByRole("button", { name: "Decrease quantity of Danger High Voltage" }),
    );
    expect(screen.getByText("1")).toBeInTheDocument();
  });

  it("removes a line", async () => {
    const user = userEvent.setup();
    renderCart([{ ...LINE, quantity: 1 }]);

    await user.click(
      screen.getByRole("button", { name: /Remove Danger High Voltage .* from cart/ }),
    );
    expect(screen.getByText("Your cart is empty")).toBeInTheDocument();
  });

  it("clears the whole cart", async () => {
    const user = userEvent.setup();
    renderCart([{ ...LINE, quantity: 1 }]);

    await user.click(screen.getByRole("button", { name: "Clear cart" }));
    expect(screen.getByText("Your cart is empty")).toBeInTheDocument();
  });
});

describe("CartView - totals", () => {
  it("sums the server prices and labels shipping and GST as pending", () => {
    renderCart([{ ...LINE, quantity: 3 }]);

    const summary = screen.getByRole("complementary", { name: "Order summary" });
    // 3 x Rs.180 = Rs.540. It appears twice - as the subtotal and as the
    // estimated total - which is correct: with shipping and GST both pending
    // the two are the same number, and showing a different one would imply we
    // know the payable amount.
    expect(within(summary).getAllByText("Rs.540")).toHaveLength(2);
    expect(within(summary).getByText("Subtotal (3 items)")).toBeInTheDocument();
    expect(within(summary).getAllByText("Calculated at checkout")).toHaveLength(2);
  });

  it("states that the total is an estimate, because the server owns the real one", () => {
    renderCart([{ ...LINE, quantity: 1 }]);

    expect(screen.getByText(/Excludes shipping and GST/)).toBeInTheDocument();
  });
});

describe("cart persistence", () => {
  it("survives a remount, so a refresh does not lose the cart", async () => {
    const first = renderCart([{ ...LINE, quantity: 2 }]);
    expect(screen.getByText("2")).toBeInTheDocument();
    first.unmount();

    render(
      <CartProvider>
        <CartView />
      </CartProvider>,
    );
    expect(screen.getByText("2")).toBeInTheDocument();
    expect(screen.getByText("Danger High Voltage")).toBeInTheDocument();
  });

  it("discards a corrupt storage value instead of crashing", () => {
    window.localStorage.setItem("spp.cart.v1", "{not json");
    expect(() =>
      render(
        <CartProvider>
          <CartView />
        </CartProvider>,
      ),
    ).not.toThrow();
    expect(screen.getByText("Your cart is empty")).toBeInTheDocument();
  });

  it("discards a stored line that has no price", () => {
    // A hand-edited or truncated entry must not produce a NaN subtotal.
    window.localStorage.setItem(
      "spp.cart.v1",
      JSON.stringify([{ variantId: "v1", productSlug: "x", quantity: 2 }]),
    );
    render(
      <CartProvider>
        <CartView />
      </CartProvider>,
    );
    expect(screen.getByText("Your cart is empty")).toBeInTheDocument();
  });
});
