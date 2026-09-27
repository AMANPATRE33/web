/**
 * Content API: industries and blog.
 *
 * Read-only wrappers over `/api/v1/industries` and `/api/v1/blog/posts`. Kept
 * separate from `catalog.ts` because the shapes are different - an industry
 * carries a Markdown body and a list of product *slugs*, a post carries an FAQ
 * block - and mixing them would invite the wrong field to be used.
 */

import { apiFetch, toParams } from "./client";
import type { Page, PageMeta } from "./types";

export interface IndustrySummary {
  id: string;
  name: string;
  slug: string;
  tagline: string | null;
  summary: string | null;
  hero_image_url: string | null;
  /** lucide-react icon name, e.g. "factory". */
  icon: string | null;
  position: number;
  product_count: number;
}

export interface IndustryDetail extends IndustrySummary {
  /** Markdown. Rendered through the sanitising subset in `components/content`. */
  body: string;
  product_slugs: string[];
  seo_title: string | null;
  seo_description: string | null;
}

export interface BlogPostSummary {
  id: string;
  title: string;
  slug: string;
  excerpt: string;
  cover_image_url: string | null;
  cover_image_alt: string | null;
  reading_minutes: number | null;
  published_at: string | null;
  seo_title: string | null;
  seo_description: string | null;
}

export interface BlogPostDetail extends BlogPostSummary {
  body: string;
  author_name: string | null;
  compliance_deadline: string | null;
  faq: Array<{ question: string; answer: string }> | null;
  related_products: Array<{ slug: string; title: string }>;
}

const CONTENT_TTL = 300;

export function listIndustries(): Promise<IndustrySummary[]> {
  return apiFetch<IndustrySummary[]>("/api/v1/industries", {
    revalidate: CONTENT_TTL,
    tags: ["industries"],
  });
}

export function getIndustry(slug: string): Promise<IndustryDetail> {
  return apiFetch<IndustryDetail>(`/api/v1/industries/${encodeURIComponent(slug)}`, {
    revalidate: CONTENT_TTL,
    tags: ["industries", `industry:${slug}`],
  });
}

export function listBlogPosts(
  options: { page?: number; perPage?: number; category?: string } = {},
): Promise<{ items: BlogPostSummary[]; meta: PageMeta }> {
  const params = toParams({
    page: options.page ?? 1,
    per_page: options.perPage ?? 12,
    category: options.category,
  });
  return apiFetch<Page<BlogPostSummary>>(`/api/v1/blog/posts?${params}`, {
    revalidate: CONTENT_TTL,
    tags: ["blog"],
  });
}

export function getBlogPost(slug: string): Promise<BlogPostDetail> {
  return apiFetch<BlogPostDetail>(`/api/v1/blog/posts/${encodeURIComponent(slug)}`, {
    revalidate: CONTENT_TTL,
    tags: ["blog", `post:${slug}`],
  });
}
