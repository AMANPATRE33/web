import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { ProductCard } from "@/components/catalog/ProductCard";
import { CartProvider } from "@/components/cart/CartProvider";
import { WishlistProvider } from "@/components/wishlist/WishlistProvider";
import type { ProductCard as ProductCardData } from "@/lib/api/types";

const push = vi.fn();
vi.mock("next/navigation", () => ({
  useRouter: () => ({ push, replace: vi.fn(), refresh: vi.fn() }),
  usePathname: () => "/shop",
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

function makeProduct(overrides: Partial<ProductCardData> = {}): ProductCardData {
  return {
    id: "p1",
    title: "Danger High Voltage",
    slug: "danger-high-voltage",
    subtitle: null,
    short_description: "Board for panel rooms.",
    brand: "Safety Poster Prints",
    sku: "SPP-ELS-001",
    category_id: "c1",
    category_name: "Electrical Safety",
    category_slug: "electrical-safety",
    price: { amount: 18_000, currency: "INR", symbol: "Rs.", formatted: "Rs.180" },
    compare_at_price: null,
    discount_percent: 0,
    is_on_sale: false,
    primary_image: {
      id: "img1",
      url: "/seed/electrical-safety/SPP-ELS-001.svg",
      alt_text: "Danger High Voltage board",
      position: 0,
      is_primary: true,
      width: 800,
      height: 800,
      blur_data_url: null,
    },
    image_count: 3,
    rating_average: 0,
    rating_count: 0,
    is_featured: false,
    tags: [],
    stock_status: "in_stock",
    in_stock: true,
    total_available: 400,
    available_colors: [],
    created_at: "2026-09-01T00:00:00Z",
    ...overrides,
  };
}

function renderCard(product: ProductCardData) {
  return render(
    <WishlistProvider>
      <CartProvider>
        <ProductCard product={product} />
      </CartProvider>
    </WishlistProvider>,
  );
}

describe("ProductCard", () => {
  it("shows the name, SKU and the server-formatted price", () => {
    renderCard(makeProduct());
    expect(screen.getByRole("heading", { name: "Danger High Voltage" })).toBeInTheDocument();
    expect(screen.getByText(/SKU SPP-ELS-001/)).toBeInTheDocument();
    expect(screen.getByText("Rs.180")).toBeInTheDocument();
  });

  it("links to the product and the category", () => {
    renderCard(makeProduct());
    expect(screen.getByRole("link", { name: /Danger High Voltage/ })).toHaveAttribute(
      "href",
      "/products/danger-high-voltage",
    );
    expect(screen.getByRole("link", { name: "Electrical Safety" })).toHaveAttribute(
      "href",
      "/category/electrical-safety",
    );
  });

  it("labels the headline price as a starting price", () => {
    // The card shows the cheapest variant, which is not the price of the board a
    // buyer usually selects. "From" is the honest label.
    renderCard(makeProduct());
    expect(screen.getByText("From")).toBeInTheDocument();
  });

  it("renders a compare-at price and a discount only when the API computed one", () => {
    renderCard(
      makeProduct({
        price: { amount: 12_000, currency: "INR", symbol: "Rs.", formatted: "Rs.120" },
        compare_at_price: {
          amount: 15_000,
          currency: "INR",
          symbol: "Rs.",
          formatted: "Rs.150",
        },
        discount_percent: 20,
        is_on_sale: true,
      }),
    );
    expect(screen.getByText("Rs.150")).toBeInTheDocument();
    expect(screen.getByText("20% off")).toBeInTheDocument();
  });

  it("never renders a zero price as if it were purchasable", () => {
    renderCard(
      makeProduct({
        price: { amount: 0, currency: "INR", symbol: "Rs.", formatted: "Rs.0" },
      }),
    );
    expect(screen.queryByText("Rs.0")).not.toBeInTheDocument();
    expect(screen.getByText("Price on request")).toBeInTheDocument();
  });

  it("shows the availability badge from the API", () => {
    renderCard(makeProduct({ in_stock: false, stock_status: "out_of_stock" }));
    expect(screen.getByText("Out of stock")).toBeInTheDocument();
  });

  it("shows no rating at all when there are no reviews", () => {
    renderCard(makeProduct({ rating_average: 0, rating_count: 0 }));
    expect(screen.queryByText("Rated")).not.toBeInTheDocument();
    expect(screen.queryByText("(0)")).not.toBeInTheDocument();
  });

  it("shows a rating when real review data exists", () => {
    renderCard(makeProduct({ rating_average: 4.5, rating_count: 12 }));
    expect(screen.getByText(/Rated 4\.5 out of 5 from 12 reviews/)).toBeInTheDocument();
  });

  it("has no add-to-cart button, because a card cannot hold a valid variant", () => {
    renderCard(makeProduct());
    expect(screen.queryByRole("button", { name: /add to cart/i })).not.toBeInTheDocument();
  });

  it("offers a wishlist toggle that toggles without navigating", async () => {
    const user = userEvent.setup();
    renderCard(makeProduct());

    const heart = screen.getByRole("button", { name: /add .* to wishlist/i });
    await user.click(heart);

    expect(
      screen.getByRole("button", { name: /remove .* from wishlist/i }),
    ).toHaveAttribute("aria-pressed", "true");
    // The card is wrapped in links; the heart must not have followed one.
    expect(push).not.toHaveBeenCalled();
  });

  it("falls back to a labelled placeholder when the image is missing", () => {
    renderCard(makeProduct({ primary_image: null }));
    expect(screen.getByText("No image")).toBeInTheDocument();
  });

  it("marks a sold-out product as such", () => {
    renderCard(makeProduct({ in_stock: false, stock_status: "out_of_stock" }));
    expect(screen.getByText("Sold out")).toBeInTheDocument();
  });
});
