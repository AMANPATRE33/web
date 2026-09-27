/**
 * Filter state lives in the URL.
 *
 * That is a product decision, not a convenience: a filtered listing is a
 * shareable, bookmarkable, crawlable page, and the browser's back button moves
 * through filter changes. It also means the server component can render the
 * first page correctly with no client JavaScript, and the filter UI can be a
 * thin controlled layer over `searchParams`.
 *
 * Multi-value filters are comma-joined rather than repeated params, so a URL
 * stays readable: `?material=3MM+ACP,5MM+FOAMSHEET`.
 */

import type { ProductQuery, ProductSort } from "./api/types";

export const SORTS: Array<{ value: ProductSort; label: string }> = [
  { value: "newest", label: "Newest" },
  { value: "price_asc", label: "Price: low to high" },
  { value: "price_desc", label: "Price: high to low" },
  { value: "popular", label: "Best selling" },
  { value: "name_asc", label: "Name: A to Z" },
];

export interface FilterState {
  page: number;
  perPage: number;
  category: string[];
  brand: string[];
  material: string[];
  size: string[];
  tag: string[];
  minPrice?: number;
  maxPrice?: number;
  inStock: boolean;
  onSale: boolean;
  sort: ProductSort;
  q: string;
}

export const DEFAULT_PER_PAGE = 24;

export function readFilters(params: URLSearchParams): FilterState {
  const list = (key: string) =>
    (params.get(key) ?? "")
      .split(",")
      .map((value) => value.trim())
      .filter(Boolean);

  const int = (key: string): number | undefined => {
    const raw = params.get(key);
    if (raw === null || raw === "") return undefined;
    const value = Number.parseInt(raw, 10);
    return Number.isFinite(value) && value >= 0 ? value : undefined;
  };

  const sort = params.get("sort") as ProductSort | null;
  const known = SORTS.map((entry) => entry.value);

  return {
    page: Math.max(1, int("page") ?? 1),
    perPage: Math.min(100, Math.max(1, int("per_page") ?? DEFAULT_PER_PAGE)),
    category: list("category"),
    brand: list("brand"),
    material: list("material"),
    size: list("size"),
    tag: list("tag"),
    minPrice: int("min_price"),
    maxPrice: int("max_price"),
    inStock: params.get("in_stock") === "true",
    onSale: params.get("on_sale") === "true",
    sort: sort && known.includes(sort) ? sort : "newest",
    q: params.get("q") ?? "",
  };
}

/** Serialise back to a query string, omitting anything at its default. */
export function writeFilters(state: Partial<FilterState>): string {
  const params = new URLSearchParams();

  const setList = (key: string, values?: string[]) => {
    if (values && values.length > 0) params.set(key, values.join(","));
  };

  if (state.page && state.page > 1) params.set("page", String(state.page));
  if (state.perPage && state.perPage !== DEFAULT_PER_PAGE) {
    params.set("per_page", String(state.perPage));
  }
  setList("category", state.category);
  setList("brand", state.brand);
  setList("material", state.material);
  setList("size", state.size);
  setList("tag", state.tag);
  if (state.minPrice !== undefined) params.set("min_price", String(state.minPrice));
  if (state.maxPrice !== undefined) params.set("max_price", String(state.maxPrice));
  if (state.inStock) params.set("in_stock", "true");
  if (state.onSale) params.set("on_sale", "true");
  if (state.sort && state.sort !== "newest") params.set("sort", state.sort);
  if (state.q) params.set("q", state.q);

  return params.toString();
}

/** To the backend's query contract. `q` becomes `q`, not `search`. */
export function toQuery(state: FilterState): ProductQuery {
  return {
    page: state.page,
    per_page: state.perPage,
    category: state.category.length ? state.category : undefined,
    brand: state.brand.length ? state.brand : undefined,
    material: state.material.length ? state.material : undefined,
    size: state.size.length ? state.size : undefined,
    tag: state.tag.length ? state.tag : undefined,
    min_price: state.minPrice,
    max_price: state.maxPrice,
    in_stock: state.inStock || undefined,
    on_sale: state.onSale || undefined,
    sort: state.sort,
    q: state.q || undefined,
  };
}

/** One toggleable chip in the active-filter row. */
export interface ActiveChip {
  key: "category" | "brand" | "material" | "size" | "tag" | "price" | "stock" | "sale";
  value: string;
  label: string;
}

export function activeChips(state: FilterState): ActiveChip[] {
  const chips: ActiveChip[] = [];
  for (const value of state.category) {
    chips.push({ key: "category", value, label: value.replace(/-/g, " ") });
  }
  for (const value of state.brand) {
    chips.push({ key: "brand", value, label: value });
  }
  for (const value of state.material) {
    chips.push({ key: "material", value, label: value });
  }
  for (const value of state.size) {
    chips.push({ key: "size", value, label: `${value} in.` });
  }
  for (const value of state.tag) {
    chips.push({ key: "tag", value, label: value.replace(/-/g, " ") });
  }
  if (state.minPrice !== undefined || state.maxPrice !== undefined) {
    chips.push({
      key: "price",
      value: "price",
      label: `₹${(state.minPrice ?? 0) / 100} – ${
        state.maxPrice === undefined ? "any" : `₹${state.maxPrice / 100}`
      }`,
    });
  }
  if (state.inStock) chips.push({ key: "stock", value: "true", label: "In stock only" });
  if (state.onSale) chips.push({ key: "sale", value: "true", label: "On sale" });
  return chips;
}

/** Apply a chip removal, returning the next state with page reset to 1. */
export function removeChip(state: FilterState, chip: ActiveChip): FilterState {
  const next: FilterState = { ...state, page: 1 };
  switch (chip.key) {
    case "category":
      next.category = state.category.filter((v) => v !== chip.value);
      break;
    case "brand":
      next.brand = state.brand.filter((v) => v !== chip.value);
      break;
    case "material":
      next.material = state.material.filter((v) => v !== chip.value);
      break;
    case "size":
      next.size = state.size.filter((v) => v !== chip.value);
      break;
    case "tag":
      next.tag = state.tag.filter((v) => v !== chip.value);
      break;
    case "price":
      next.minPrice = undefined;
      next.maxPrice = undefined;
      break;
    case "stock":
      next.inStock = false;
      break;
    case "sale":
      next.onSale = false;
      break;
  }
  return next;
}

/** Toggle a multi-value filter. Any change resets to page 1. */
export function toggleValue(
  state: FilterState,
  key: "category" | "brand" | "material" | "size" | "tag",
  value: string,
): FilterState {
  const current = state[key];
  const next = current.includes(value)
    ? current.filter((v) => v !== value)
    : [...current, value];
  return { ...state, [key]: next, page: 1 };
}
