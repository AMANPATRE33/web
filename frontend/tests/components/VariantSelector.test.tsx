import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { VariantSelector } from "@/components/product/VariantSelector";
import { CartProvider, useCart } from "@/components/cart/CartProvider";
import type { ProductDetail, Variant, VariantOption } from "@/lib/api/types";

const push = vi.fn();
vi.mock("next/navigation", () => ({
  useRouter: () => ({ push, replace: vi.fn(), refresh: vi.fn() }),
  usePathname: () => "/products/danger-high-voltage",
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

// ---------------------------------------------------------------------------
// Fixture: an irregular matrix, matching the shape of the real seeded data.
//   ACP:    8x12, 18x24, 24x36, 48x96
//   Vinyl:  8x12, 18x24
//   Autoglow: 12x18, 18x24
// ---------------------------------------------------------------------------

function variant(material: string, size: string, price: number, inStock = true): Variant {
  return {
    id: `${material}|${size}`,
    sku: `SPP-TEST-${material.replace(/ /g, "")}-${size}`,
    title: `${size} - ${material}`,
    attributes: { Size: size, Material: material },
    price: { amount: price, currency: "INR", symbol: "Rs.", formatted: `Rs.${price / 100}` },
    compare_at_price: null,
    discount_percent: 0,
    currency: "INR",
    status: "ACTIVE",
    is_default: material === "3MM ACP" && size === "8x12",
    available_quantity: inStock ? 40 : 0,
    in_stock: inStock,
    low_stock: false,
    options: { Size: size, Material: material },
  };
}

function axis(name: string, values: string[], variants: Variant[]): VariantOption {
  return {
    name,
    values,
    variant_ids_by_value: Object.fromEntries(
      values.map((value) => [
        value,
        variants.filter((v) => v.attributes[name] === value).map((v) => v.id),
      ]),
    ),
  };
}

function makeProduct(overrides: Partial<ProductDetail> = {}): ProductDetail {
  const variants = [
    variant("3MM ACP", "8x12", 10_000),
    variant("3MM ACP", "18x24", 18_000),
    variant("3MM ACP", "24x36", 27_000),
    variant("3MM ACP", "48x96", 88_000),
    variant("ECO VINYL STICKER", "8x12", 4_000),
    variant("ECO VINYL STICKER", "18x24", 6_000),
    variant("AUTOGLOW STICKER", "12x18", 12_000),
    variant("AUTOGLOW STICKER", "18x24", 16_000),
  ];

  return {
    id: "p1",
    title: "Danger High Voltage",
    slug: "danger-high-voltage",
    subtitle: null,
    short_description: "Board",
    description: "Board",
    sku: "SPP-ELS-001",
    brand: "Safety Poster Prints",
    category: {
      id: "c1",
      name: "Electrical Safety",
      slug: "electrical-safety",
      parent_id: null,
      image_url: null,
      position: 1,
    },
    breadcrumb: [],
    price: variants[4].price,
    compare_at_price: null,
    discount_percent: 0,
    min_price: variants[4].price,
    max_price: variants[3].price,
    specs: {},
    tags: [],
    images: [],
    variants,
    options: [
      axis("Material", ["3MM ACP", "ECO VINYL STICKER", "AUTOGLOW STICKER"], variants),
      axis("Size", ["8x12", "12x18", "18x24", "24x36", "48x96"], variants),
    ],
    rating_average: 0,
    rating_count: 0,
    rating_distribution: {},
    is_featured: false,
    status: "ACTIVE",
    stock_status: "in_stock",
    in_stock: true,
    total_available: 320,
    seo_title: null,
    seo_description: null,
    created_at: null,
    updated_at: null,
    ...overrides,
  };
}

/** Surfaces the cart so assertions can read real state, not a mock. */
function CartProbe() {
  const { lines, itemCount } = useCart();
  return (
    <div data-testid="cart">
      <span data-testid="cart-count">{itemCount}</span>
      <ul>
        {lines.map((line) => (
          <li key={line.variantId} data-testid="cart-line">
            {line.material} / {line.size} / {line.variantSku} x{line.quantity} @{" "}
            {line.unitPrice.formatted}
          </li>
        ))}
      </ul>
    </div>
  );
}

function renderSelector(product = makeProduct()) {
  return render(
    <CartProvider>
      <VariantSelector product={product} />
      <CartProbe />
    </CartProvider>,
  );
}

/** The button for one option value, scoped to its axis group. */
function optionFor(groupLabel: string, value: string): HTMLButtonElement {
  const group = screen.getByRole("radiogroup", { name: groupLabel });
  return within(group).getByRole("radio", { name: new RegExp(value, "i") });
}

beforeEach(() => {
  push.mockClear();
});

describe("VariantSelector - initial state", () => {
  it("renders exactly the materials and sizes the API returned", () => {
    renderSelector();
    const material = screen.getByRole("radiogroup", { name: "Material" });
    const size = screen.getByRole("radiogroup", { name: "Size" });

    expect(within(material).getAllByRole("radio")).toHaveLength(3);
    expect(within(size).getAllByRole("radio")).toHaveLength(5);
  });

  it("starts on the default variant, so the shown price is the price bought", () => {
    renderSelector();
    expect(optionFor("Material", "3MM ACP")).toHaveAttribute("aria-checked", "true");
    expect(optionFor("Size", "8x12")).toHaveAttribute("aria-checked", "true");
    expect(screen.getByText("Rs.100")).toBeInTheDocument();
    expect(screen.getByText("SKU SPP-TEST-3MMACP-8x12")).toBeInTheDocument();
  });

  it("marks Size as required, not optional", () => {
    renderSelector();
    const legend = screen.getByRole("group", { name: /Size/ });
    expect(within(legend).getByText("*")).toBeInTheDocument();
  });
});

describe("VariantSelector - material changes available sizes", () => {
  it("disables a size the selected material is not made in", () => {
    // The default selection is ACP / 8x12, and ACP has no 12x18 variant, so
    // 12x18 is a combination the business does not sell and must be disabled
    // rather than selectable-then-failing.
    renderSelector();
    expect(optionFor("Size", "12x18")).toBeDisabled();
    expect(optionFor("Size", "8x12")).toBeEnabled();
    expect(optionFor("Size", "18x24")).toBeEnabled();
    expect(optionFor("Size", "24x36")).toBeEnabled();
    expect(optionFor("Size", "48x96")).toBeEnabled();
  });

  it("disables more sizes as the material narrows", async () => {
    const user = userEvent.setup();
    renderSelector();

    // 18x24 is available in all three materials, so it is a common pivot.
    await user.click(optionFor("Size", "18x24"));
    expect(optionFor("Size", "48x96")).toBeEnabled();

    // Vinyl is only made in 8x12 and 18x24.
    await user.click(optionFor("Material", "ECO VINYL STICKER"));
    expect(optionFor("Size", "12x18")).toBeDisabled();
    expect(optionFor("Size", "24x36")).toBeDisabled();
    expect(optionFor("Size", "48x96")).toBeDisabled();
    expect(optionFor("Size", "8x12")).toBeEnabled();
    expect(optionFor("Size", "18x24")).toBeEnabled();
  });

  it("explains why an option is greyed out, rather than leaving the customer guessing", () => {
    renderSelector();
    // 12x18 is disabled because the current material has no 12x18 variant. The
    // note is the difference between "we don't make this" and "pick another
    // material first".
    expect(
      screen.getByText(/not available with material/i),
    ).toBeInTheDocument();
  });

  it("offers a material that shares the chosen size", async () => {
    const user = userEvent.setup();
    renderSelector();

    await user.click(optionFor("Size", "18x24"));
    // All three materials are made in 18x24, so all are selectable.
    expect(optionFor("Material", "3MM ACP")).toBeEnabled();
    expect(optionFor("Material", "ECO VINYL STICKER")).toBeEnabled();
    expect(optionFor("Material", "AUTOGLOW STICKER")).toBeEnabled();
  });

  it("makes a material reachable by changing the size to one it is made in", async () => {
    const user = userEvent.setup();
    renderSelector();

    // Autoglow exists only in 12x18 and 18x24, so it is genuinely unavailable
    // at the default 8x12. 18x24 is available under ACP, so switching to it
    // makes Autoglow selectable. This is the escape hatch: the state is never
    // a dead end, it just takes a different order of clicks.
    expect(optionFor("Material", "AUTOGLOW STICKER")).toBeDisabled();

    await user.click(optionFor("Size", "18x24"));
    expect(optionFor("Material", "AUTOGLOW STICKER")).toBeEnabled();

    await user.click(optionFor("Material", "AUTOGLOW STICKER"));
    expect(optionFor("Size", "18x24")).toHaveAttribute("aria-checked", "true");
    expect(screen.getByText("SKU SPP-TEST-AUTOGLOWSTICKER-18x24")).toBeInTheDocument();
  });

  it("keeps a size that the new material does support", async () => {
    const user = userEvent.setup();
    renderSelector();

    await user.click(optionFor("Size", "18x24"));
    await user.click(optionFor("Material", "ECO VINYL STICKER"));

    expect(optionFor("Size", "18x24")).toHaveAttribute("aria-checked", "true");
    expect(screen.getByText("SKU SPP-TEST-ECOVINYLSTICKER-18x24")).toBeInTheDocument();
    expect(screen.getByText("Rs.60")).toBeInTheDocument();
  });
});

describe("VariantSelector - price, SKU and stock follow the selection", () => {
  it("updates the price when the size changes", async () => {
    const user = userEvent.setup();
    renderSelector();

    expect(screen.getByText("Rs.100")).toBeInTheDocument();
    await user.click(optionFor("Size", "48x96"));
    expect(screen.getByText("Rs.880")).toBeInTheDocument();
    expect(screen.queryByText("Rs.100")).not.toBeInTheDocument();
  });

  it("updates the price when the material changes", async () => {
    const user = userEvent.setup();
    renderSelector();

    await user.click(optionFor("Size", "8x12"));
    await user.click(optionFor("Material", "ECO VINYL STICKER"));
    expect(screen.getByText("Rs.40")).toBeInTheDocument();
  });

  it("labels the price as being for the selected combination", async () => {
    const user = userEvent.setup();
    renderSelector();
    await user.click(optionFor("Size", "24x36"));
    expect(screen.getByText(/3MM ACP \/ 24x36/)).toBeInTheDocument();
  });
});

describe("VariantSelector - add to cart", () => {
  it("is enabled for the default, in-stock combination", () => {
    renderSelector();
    expect(screen.getByRole("button", { name: "Add to cart" })).toBeEnabled();
  });

  it("stays disabled when the only matching variant is sold out", async () => {
    // The reachable version of "cannot buy this". Because incompatible options
    // are disabled rather than selectable, an incomplete selection is not
    // reachable through the UI - so the guard is exercised through stock.
    const user = userEvent.setup();
    const product = makeProduct();
    product.variants = product.variants.map((v) =>
      v.attributes.Size === "48x96" ? { ...v, in_stock: false, available_quantity: 0 } : v,
    );

    renderSelector(product);
    await user.click(optionFor("Size", "48x96"));

    expect(screen.getByRole("button", { name: "Select an option" })).toBeDisabled();
    expect(screen.getByRole("status")).toHaveTextContent(
      "This option is sold out. Try another size or material.",
    );
  });

  it("shows the reason whenever the button is disabled", async () => {
    const user = userEvent.setup();
    const product = makeProduct();
    product.variants = product.variants.map((v) => ({ ...v, in_stock: false, available_quantity: 0 }));

    renderSelector(product);
    await user.click(optionFor("Size", "18x24"));

    expect(screen.getByRole("button", { name: "Select an option" })).toBeDisabled();
    expect(screen.getByRole("status").textContent?.length).toBeGreaterThan(10);
  });

  it("adds the selected variant, not the default one", async () => {
    const user = userEvent.setup();
    renderSelector();

    await user.click(optionFor("Size", "48x96"));
    await user.click(screen.getByRole("button", { name: "Add to cart" }));

    const line = screen.getByTestId("cart-line");
    expect(line).toHaveTextContent("3MM ACP / 48x96 / SPP-TEST-3MMACP-48x96 x1 @ Rs.880");
  });

  it("adds the chosen quantity", async () => {
    const user = userEvent.setup();
    renderSelector();

    // Twenty-four clicks is slow and brittle; set the field directly the way a
    // keyboard user would, then confirm the value took.
    const quantity = screen.getByLabelText("Quantity");
    await user.clear(quantity);
    await user.type(quantity, "25");
    expect((quantity as HTMLInputElement).value).toBe("25");

    await user.click(screen.getByRole("button", { name: "Add to cart" }));
    expect(screen.getByTestId("cart-line")).toHaveTextContent("x25");
    expect(screen.getByTestId("cart-count")).toHaveTextContent("25");
  });

  it("adds a quantity chosen with the stepper", async () => {
    const user = userEvent.setup();
    renderSelector();

    await user.click(screen.getByRole("button", { name: "Increase quantity" }));
    await user.click(screen.getByRole("button", { name: "Increase quantity" }));
    await user.click(screen.getByRole("button", { name: "Add to cart" }));

    expect(screen.getByTestId("cart-line")).toHaveTextContent("x3");
  });

  it("confirms what was added, naming the combination", async () => {
    const user = userEvent.setup();
    renderSelector();
    await user.click(optionFor("Size", "24x36"));
    await user.click(screen.getByRole("button", { name: "Add to cart" }));
    expect(screen.getByRole("status")).toHaveTextContent(
      "Added 3MM ACP / 24x36 to cart.",
    );
  });

  it("does not add the same variant as two lines", async () => {
    const user = userEvent.setup();
    renderSelector();

    await user.click(screen.getByRole("button", { name: "Add to cart" }));
    await user.click(screen.getByRole("button", { name: "Add to cart" }));

    expect(screen.getAllByTestId("cart-line")).toHaveLength(1);
    // ...but the quantity goes up, because it is the same thing.
    expect(screen.getByTestId("cart-line")).toHaveTextContent("x2");
  });

  it("keeps different variants of the same product as separate lines", async () => {
    const user = userEvent.setup();
    renderSelector();

    await user.click(optionFor("Size", "8x12"));
    await user.click(screen.getByRole("button", { name: "Add to cart" }));

    await user.click(optionFor("Size", "18x24"));
    await user.click(screen.getByRole("button", { name: "Add to cart" }));

    // Same product, different size: two lines, because they are manufactured
    // and priced separately.
    expect(screen.getAllByTestId("cart-line")).toHaveLength(2);
  });
});

describe("VariantSelector - quantity stepper", () => {
  it("increments and decrements", async () => {
    const user = userEvent.setup();
    renderSelector();

    await user.click(screen.getByRole("button", { name: "Increase quantity" }));
    expect((screen.getByLabelText("Quantity") as HTMLInputElement).value).toBe("2");

    await user.click(screen.getByRole("button", { name: "Decrease quantity" }));
    expect((screen.getByLabelText("Quantity") as HTMLInputElement).value).toBe("1");
  });

  it("will not go below one", async () => {
    renderSelector();
    expect(screen.getByRole("button", { name: "Decrease quantity" })).toBeDisabled();
  });
});

describe("VariantSelector - sold out variants", () => {
  it("labels an option that exists but has no stock", () => {
    const product = makeProduct();
    product.variants = product.variants.map((v) =>
      v.attributes.Size === "48x96" ? { ...v, in_stock: false, available_quantity: 0 } : v,
    );
    renderSelector(product);
    // Present but unavailable, rather than hidden: the customer learns the
    // size exists instead of wondering whether it is a typo.
    expect(optionFor("Size", "48x96")).toBeEnabled();
  });

  it("reports remaining stock for an in-stock option", () => {
    renderSelector();
    expect(screen.getByText(/40 available/)).toBeInTheDocument();
  });
});
