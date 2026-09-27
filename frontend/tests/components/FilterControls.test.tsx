import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { FilterControls, ActiveFilterChips, SortSelect } from "@/components/filters/FilterControls";
import type { Category, Facets } from "@/lib/api/types";

/**
 * Filter behaviour.
 *
 * The contract these tests pin down: filters are *state in the URL*, and every
 * change is a `router.push` with `scroll: false`. There is no client-side copy
 * of the product list, so a filter that fails to reach the URL cannot appear to
 * have been applied. That is the property worth testing - not the rendering.
 */

let searchParams = new URLSearchParams();
const push = vi.fn();

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push, replace: vi.fn(), refresh: vi.fn(), prefetch: vi.fn() }),
  usePathname: () => "/shop",
  useSearchParams: () => searchParams,
  useTransition: () => [false, (fn: () => void) => fn()],
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

const CATEGORIES: Category[] = [
  {
    id: "c1",
    name: "Electrical Safety",
    slug: "electrical-safety",
    parent_id: null,
    image_url: null,
    position: 1,
    description: null,
    seo_title: null,
    seo_description: null,
    children: [],
    ancestors: [],
    product_count: 10,
    path: "",
  },
  {
    id: "c2",
    name: "MSDS",
    slug: "msds",
    parent_id: null,
    image_url: null,
    position: 2,
    description: null,
    seo_title: null,
    seo_description: null,
    children: [],
    ancestors: [],
    product_count: 52,
    path: "",
  },
];

const FACETS: Facets = {
  brands: [{ value: "Safety Poster Prints", count: 105 }],
  tags: [{ slug: "iso7010", name: "ISO 7010", count: 40 }],
  materials: [
    { value: "3MM ACP", count: 105 },
    { value: "5MM FOAMSHEET", count: 98 },
    { value: "AUTOGLOW STICKER", count: 60 },
    { value: "ECO VINYL STICKER", count: 80 },
  ],
  sizes: [
    { value: "8x12", count: 40 },
    { value: "12x18", count: 60 },
    { value: "18x24", count: 95 },
    { value: "24x36", count: 70 },
    { value: "48x96", count: 12 },
  ],
  price_range: { min: 8_000, max: 880_000 },
};

function setParams(query: string) {
  searchParams = new URLSearchParams(query);
}

function renderSidebar(props: Partial<React.ComponentProps<typeof FilterControls>> = {}) {
  return render(
    <FilterControls facets={FACETS} categories={CATEGORIES} {...props} />,
  );
}

function lastPush(): string {
  const call = push.mock.calls.at(-1);
  if (!call) throw new Error("router.push was never called");
  return call[0] as string;
}

describe("FilterControls", () => {
  it("lists every material and size the facets endpoint returned", () => {
    setParams("");
    renderSidebar();

    for (const material of FACETS.materials) {
      expect(screen.getByText(material.value)).toBeInTheDocument();
    }
    for (const size of FACETS.sizes) {
      expect(screen.getByText(size.value)).toBeInTheDocument();
    }
  });

  it("shows the facet count next to each option", () => {
    setParams("");
    renderSidebar();
    expect(screen.getByText("105")).toBeInTheDocument();
    expect(screen.getByText("12")).toBeInTheDocument();
  });

  it("writes a material selection into the URL and ticks immediately", async () => {
    const user = userEvent.setup();
    setParams("");
    renderSidebar();

    const checkbox = screen.getByRole("checkbox", { name: /3MM ACP/ });
    expect(checkbox).not.toBeChecked();

    await user.click(checkbox);

    expect(lastPush()).toContain("material=3MM+ACP");
    // Optimistic: the box ticks without waiting for the server round trip that
    // updates `searchParams`. Playwright caught the un-optimistic version as a
    // control that appeared to do nothing.
    // Re-queried, because the click re-renders and replaces the DOM node.
    expect(screen.getByRole("checkbox", { name: /3MM ACP/ })).toBeChecked();
  });

  it("shows the optimistic value only until the URL catches up", async () => {
    const user = userEvent.setup();
    setParams("");
    const { unmount } = renderSidebar();

    await user.click(screen.getByRole("checkbox", { name: /3MM ACP/ }));
    unmount();

    // Fresh mount with the server now reporting the filter: state is read from
    // the URL, with no leftover override.
    setParams("material=3MM+ACP");
    renderSidebar();
    expect(screen.getAllByRole("checkbox", { name: /3MM ACP/ })[0]).toBeChecked();
  });

  it("writes a size selection into the URL", async () => {
    const user = userEvent.setup();
    setParams("");
    renderSidebar();

    await user.click(screen.getByRole("checkbox", { name: /18x24/ }));
    expect(lastPush()).toContain("size=18x24");
  });

  it("writes a category selection into the URL", async () => {
    const user = userEvent.setup();
    setParams("");
    renderSidebar();

    await user.click(screen.getByRole("checkbox", { name: "MSDS" }));
    expect(lastPush()).toContain("category=msds");
  });

  it("appends rather than replaces, so a second filter combines with the first", async () => {
    const user = userEvent.setup();
    setParams("material=3MM%20ACP");
    renderSidebar();

    await user.click(screen.getByRole("checkbox", { name: /18x24/ }));
    const next = lastPush();
    expect(next).toContain("material=");
    expect(next).toContain("size=18x24");
  });

  it("ticks a filter that arrived in the URL before the user touched it", () => {
    setParams("material=3MM%20ACP");
    renderSidebar();
    // Read straight from server state; the optimistic override only exists for
    // the gap between a click and the navigation landing.
    expect(screen.getByRole("checkbox", { name: /3MM ACP/ })).toBeChecked();
  });

  it("removes a value when an already-selected filter is clicked", async () => {
    const user = userEvent.setup();
    setParams("material=3MM+ACP");
    renderSidebar();

    const checkbox = screen.getByRole("checkbox", { name: /3MM ACP/ });
    expect(checkbox).toBeChecked();

    await user.click(checkbox);
    // Both filters are gone, so the query string is empty and we navigate to
    // the bare path rather than to "?".
    expect(lastPush()).toBe("/shop");
  });

  it("resets to page 1 when a filter changes", async () => {
    const user = userEvent.setup();
    setParams("page=5");
    renderSidebar();

    await user.click(screen.getByRole("checkbox", { name: /18x24/ }));
    // page=5 must not survive: page 5 of the new result set is meaningless.
    expect(lastPush()).not.toContain("page=5");
  });

  it("toggles the availability filters", async () => {
    const user = userEvent.setup();
    setParams("");
    renderSidebar();

    await user.click(screen.getByRole("checkbox", { name: "In stock only" }));
    expect(lastPush()).toContain("in_stock=true");
  });

  it("reflects the current URL state on the checkboxes", () => {
    setParams("material=3MM+ACP,5MM+FOAMSHEET&size=48x96");
    renderSidebar();

    expect(screen.getByRole("checkbox", { name: /3MM ACP/ })).toBeChecked();
    expect(screen.getByRole("checkbox", { name: /5MM FOAMSHEET/ })).toBeChecked();
    expect(screen.getByRole("checkbox", { name: /48x96/ })).toBeChecked();
    expect(screen.getByRole("checkbox", { name: /18x24/ })).not.toBeChecked();
  });

  it("hides the category facet on a category page, where it is redundant", () => {
    setParams("");
    renderSidebar({ hideCategory: true });
    expect(screen.queryByRole("checkbox", { name: "MSDS" })).not.toBeInTheDocument();
  });

  it("offers a mobile filter trigger that reports the active count", () => {
    setParams("material=3MM+ACP&size=18x24");
    renderSidebar();
    expect(screen.getByRole("button", { name: /Filters/ })).toHaveTextContent("2");
  });

  it("shows the catalogue price range so the buyer knows the bounds", () => {
    setParams("");
    renderSidebar();
    expect(screen.getByText(/Catalogue range Rs\.80 to Rs\.8,800/)).toBeInTheDocument();
  });
});

describe("ActiveFilterChips", () => {
  it("renders nothing when no filter is active", () => {
    setParams("");
    render(<ActiveFilterChips chips={[]} />);
    expect(screen.queryByRole("button", { name: /Remove filter/ })).not.toBeInTheDocument();
  });

  it("removes just the clicked filter", async () => {
    const user = userEvent.setup();
    setParams("material=3MM+ACP&size=18x24");
    render(
      <ActiveFilterChips
        chips={[
          { key: "material", value: "3MM ACP", label: "3MM ACP" },
          { key: "size", value: "18x24", label: "18x24 in." },
        ]}
      />,
    );

    const [firstChip] = screen.getAllByRole("button", { name: /Remove filter/ });
    await user.click(firstChip);

    expect(lastPush()).not.toContain("material=");
    expect(lastPush()).toContain("size=18x24");
  });
});

describe("SortSelect", () => {
  it("writes the selected sort and drops the default", async () => {
    const user = userEvent.setup();
    setParams("");
    render(<SortSelect />);

    await user.selectOptions(screen.getByLabelText("Sort"), "price_asc");
    expect(lastPush()).toContain("sort=price_asc");
  });

  it("omits sort=newest so the URL stays clean", async () => {
    const user = userEvent.setup();
    setParams("sort=price_asc");
    render(<SortSelect />);

    await user.selectOptions(screen.getByLabelText("Sort"), "newest");
    expect(lastPush()).toBe("/shop");
  });

  it("keeps other filters when the sort changes", async () => {
    const user = userEvent.setup();
    setParams("material=3MM+ACP&page=4");
    render(<SortSelect />);

    await user.selectOptions(screen.getByLabelText("Sort"), "price_desc");
    const next = lastPush();
    expect(next).toContain("sort=price_desc");
    expect(next).toContain("material=");
    // Changing the sort returns the customer to the first page of the new order.
    expect(next).not.toContain("page=4");
  });
});
