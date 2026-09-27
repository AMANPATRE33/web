/**
 * Catalogue endpoints. One function per API route, so a component never builds
 * a URL and the query-parameter shape lives in exactly one place.
 *
 * Server-side calls are cached briefly (a few seconds) because the catalogue
 * changes rarely and a listing page is the hottest path. Product detail uses
 * tag-based revalidation so an admin edit can purge it precisely rather than
 * waiting for a TTL.
 */

import { apiFetch, toParams } from "./client";
import type {
  Category,
  Facets,
  Page,
  ProductCard,
  ProductDetail,
  ProductQuery,
  RelatedProduct,
  SearchResponse,
  SearchSuggestion,
} from "./types";

/** Catalogue changes at most a few times a day. 30s is imperceptible to a shopper. */
const LIST_TTL = 30;

export function listProducts(
  query: ProductQuery = {},
  options: { token?: string | null; signal?: AbortSignal } = {},
): Promise<Page<ProductCard>> {
  const params = toParams({ ...query });
  return apiFetch<Page<ProductCard>>(`/api/v1/products?${params}`, {
    revalidate: LIST_TTL,
    tags: ["products"],
    ...options,
  });
}

export function getProduct(
  slug: string,
  options: { token?: string | null; signal?: AbortSignal } = {},
): Promise<ProductDetail> {
  return apiFetch<ProductDetail>(`/api/v1/products/${encodeURIComponent(slug)}`, {
    revalidate: LIST_TTL,
    tags: ["products", `product:${slug}`],
    ...options,
  });
}

export function getRelatedProducts(
  slug: string,
  limit = 8,
): Promise<RelatedProduct[]> {
  const params = toParams({ limit });
  return apiFetch<RelatedProduct[]>(
    `/api/v1/products/${encodeURIComponent(slug)}/related?${params}`,
    { revalidate: LIST_TTL, tags: ["products"] },
  );
}

export function listCategories(): Promise<Category[]> {
  return apiFetch<Category[]>("/api/v1/categories", {
    revalidate: 300,
    tags: ["categories"],
  });
}

export function getCategory(slug: string): Promise<Category> {
  return apiFetch<Category>(`/api/v1/categories/${encodeURIComponent(slug)}`, {
    revalidate: 300,
    tags: ["categories", `category:${slug}`],
  });
}

/** Facet counts scoped to a category, or the whole catalogue when no slug. */
export function getFacets(categorySlug?: string): Promise<Facets> {
  const path = categorySlug
    ? `/api/v1/categories/${encodeURIComponent(categorySlug)}/facets`
    : "/api/v1/facets";
  return apiFetch<Facets>(path, { revalidate: 300, tags: ["facets", "categories"] });
}

export function searchCatalogue(
  q: string,
  options: { page?: number; perPage?: number; type?: "all" | "product" | "category" } = {},
): Promise<SearchResponse> {
  const params = toParams({
    q,
    page: options.page ?? 1,
    per_page: options.perPage ?? 24,
    type: options.type ?? "all",
  });
  return apiFetch<SearchResponse>(`/api/v1/search?${params}`, {
    revalidate: 15,
    tags: ["search"],
  });
}

export function getSearchSuggestions(q: string, limit = 8): Promise<SearchSuggestion[]> {
  const params = toParams({ q, limit });
  return apiFetch<SearchSuggestion[]>(`/api/v1/search/suggestions?${params}`, {
    revalidate: 60,
    tags: ["search"],
  });
}

export function getFeatured(limit = 8): Promise<ProductCard[]> {
  return apiFetch<ProductCard[]>(`/api/v1/products/featured?${toParams({ limit })}`, {
    revalidate: LIST_TTL,
    tags: ["products"],
  });
}

export function getNewArrivals(limit = 8): Promise<ProductCard[]> {
  return apiFetch<ProductCard[]>(`/api/v1/products/new?${toParams({ limit })}`, {
    revalidate: LIST_TTL,
    tags: ["products"],
  });
}

export function getBestSellers(limit = 8): Promise<ProductCard[]> {
  return apiFetch<ProductCard[]>(
    `/api/v1/products/best-sellers?${toParams({ limit })}`,
    { revalidate: LIST_TTL, tags: ["products"] },
  );
}

export function getPopularSearches(): Promise<string[]> {
  return apiFetch<string[]>("/api/v1/search/trending", { revalidate: 3600 });
}
