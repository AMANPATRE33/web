/**
 * TypeScript types mirroring the backend Pydantic schemas.
 *
 * These were written against the real API responses, not from the schema
 * definitions alone - see `backend/app/scripts/dump_api_contract.py`, which
 * dumps actual payloads to `.local/api-contract/`. Keeping them hand-written
 * rather than generated is a deliberate trade: the surface is small and stable,
 * and a codegen step would add a build dependency for 12 interfaces.
 *
 * Naming follows the wire format exactly. If a field is renamed on the
 * backend, TypeScript will fail the build here rather than silently rendering
 * `undefined` in the UI.
 */

// ---------------------------------------------------------------------------
// Envelope
// ---------------------------------------------------------------------------
export interface PageMeta {
  page: number;
  per_page: number;
  total: number;
  total_pages: number;
  has_next: boolean;
  has_previous: boolean;
}

export interface Page<T> {
  items: T[];
  meta: PageMeta;
}

/** Every error from the API uses this shape. See app/core/errors.py. */
export interface ApiErrorBody {
  code: string;
  message: string;
  field_errors?: Record<string, string[]>;
  details?: Record<string, unknown>;
  request_id?: string;
}

// ---------------------------------------------------------------------------
// Money
// ---------------------------------------------------------------------------
/**
 * Amounts are integer minor units (paise) end to end. `formatted` is produced
 * by the backend so the server and client can never disagree on display, and
 * so Indian digit grouping is applied in exactly one place.
 */
export interface Money {
  amount: number;
  currency: string;
  symbol: string;
  formatted: string;
}

// ---------------------------------------------------------------------------
// Catalogue
// ---------------------------------------------------------------------------
export type StockStatus = "in_stock" | "low_stock" | "out_of_stock" | "preorder";

export type ProductSort =
  | "relevance"
  | "newest"
  | "oldest"
  | "price_asc"
  | "price_desc"
  | "rating"
  | "popular"
  | "name_asc"
  | "name_desc";

export interface ProductImage {
  id: string;
  url: string;
  alt_text: string;
  position: number;
  is_primary: boolean;
  width: number | null;
  height: number | null;
  blur_data_url: string | null;
}

export interface Variant {
  id: string;
  sku: string;
  title: string;
  /** e.g. `{ Size: "18x24", Material: "3MM ACP" }` */
  attributes: Record<string, string>;
  price: Money;
  compare_at_price: Money | null;
  discount_percent: number;
  currency: string;
  status: string;
  is_default: boolean;
  available_quantity: number;
  in_stock: boolean;
  low_stock: boolean;
  options: Record<string, string>;
}

/**
 * One axis of the variant matrix, with the variant ids that carry each value.
 *
 * `variant_ids_by_value` is what lets the UI disable a Size that the selected
 * Material is not sold in, instead of letting a shopper pick a combination
 * that does not exist and failing at checkout.
 */
export interface VariantOption {
  name: string;
  values: string[];
  variant_ids_by_value: Record<string, string[]>;
}

export interface ProductCard {
  id: string;
  title: string;
  slug: string;
  subtitle: string | null;
  short_description: string | null;
  brand: string | null;
  sku: string;
  category_id: string;
  category_name: string;
  category_slug: string;
  price: Money;
  compare_at_price: Money | null;
  discount_percent: number;
  is_on_sale: boolean;
  primary_image: ProductImage | null;
  image_count: number;
  rating_average: number;
  rating_count: number;
  is_featured: boolean;
  tags: string[];
  stock_status: StockStatus;
  in_stock: boolean;
  total_available: number;
  available_colors: string[];
  created_at: string | null;
}

export interface ProductDetail {
  id: string;
  title: string;
  slug: string;
  subtitle: string | null;
  short_description: string | null;
  description: string;
  sku: string;
  brand: string | null;
  category: CategorySummary;
  /** Empty for this catalogue: the live taxonomy is flat. */
  breadcrumb: CategorySummary[];
  price: Money;
  compare_at_price: Money | null;
  discount_percent: number;
  min_price: Money | null;
  max_price: Money | null;
  specs: Record<string, string>;
  tags: string[];
  images: ProductImage[];
  variants: Variant[];
  options: VariantOption[];
  rating_average: number;
  rating_count: number;
  rating_distribution: Record<string, number>;
  is_featured: boolean;
  status: string;
  stock_status: StockStatus;
  in_stock: boolean;
  total_available: number;
  seo_title: string | null;
  seo_description: string | null;
  created_at: string | null;
  updated_at: string | null;
}

export interface CategorySummary {
  id: string;
  name: string;
  slug: string;
  parent_id: string | null;
  image_url: string | null;
  position: number;
}

export interface Category extends CategorySummary {
  description: string | null;
  seo_title: string | null;
  seo_description: string | null;
  children: CategorySummary[];
  ancestors: CategorySummary[];
  product_count: number;
  path: string;
}

export interface FacetOption {
  value: string;
  count: number;
}

export interface Facets {
  brands: FacetOption[];
  tags: Array<{ slug: string; name: string; count: number }>;
  materials: FacetOption[];
  sizes: FacetOption[];
  price_range: { min: number; max: number };
}

export interface SearchSuggestion {
  text: string;
  type: "product" | "category" | "brand" | "tag";
  slug: string | null;
  product_id: string | null;
}

export interface SearchResultItem {
  type: "product" | "category";
  id: string;
  title: string;
  slug: string;
  subtitle: string | null;
  image_url: string | null;
  price: Money | null;
  in_stock: boolean;
}

export interface SearchResponse {
  query: string;
  items: SearchResultItem[];
  meta: PageMeta;
  count: number;
}

export interface RelatedProduct {
  id: string;
  title: string;
  slug: string;
  brand: string | null;
  price: Money;
  compare_at_price: Money | null;
  discount_percent: number;
  primary_image: ProductImage | null;
  in_stock: boolean;
  rating_average: number;
  rating_count: number;
  reason: string | null;
}

// ---------------------------------------------------------------------------
// Filters
// ---------------------------------------------------------------------------
export interface ProductQuery {
  page?: number;
  per_page?: number;
  category?: string[];
  brand?: string[];
  tag?: string[];
  /** Explicit slugs, returned in the order given. For curated pages. */
  slug?: string[];
  material?: string[];
  size?: string[];
  min_price?: number;
  max_price?: number;
  in_stock?: boolean;
  on_sale?: boolean;
  featured?: boolean;
  sort?: ProductSort;
  q?: string;
}
