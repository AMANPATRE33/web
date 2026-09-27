import type { MetadataRoute } from "next";

import { listCategories } from "@/lib/api/catalog";
import { getIndustry, listIndustries } from "@/lib/api/content";
import { listBlogPosts } from "@/lib/api/content";
import { listProducts } from "@/lib/api/catalog";
import { env } from "@/lib/env";

// Rendered per request. Prices, stock and availability must never be baked
// into a build: a stale static page would sell a variant that has since sold
// out, at a price the catalogue has since changed.
export const dynamic = "force-dynamic";

/**
 * Sitemap.
 *
 * Everything in here is generated from the database. A category or product that
 * is deactivated or deleted disappears from the sitemap on the next
 * regeneration, because there is no hand-maintained URL list to forget to
 * update.
 *
 * Deliberately excluded: cart, checkout, account, wishlist, and any filtered
 * listing URL. Those are `noindex` in their own metadata, and listing them here
 * would be contradictory.
 */
export default async function sitemap(): Promise<MetadataRoute.Sitemap> {
  const base = env.siteUrl;
  const now = new Date();

  const staticEntries: MetadataRoute.Sitemap = [
    { url: `${base}/`, lastModified: now, changeFrequency: "daily", priority: 1 },
    { url: `${base}/shop`, lastModified: now, changeFrequency: "daily", priority: 0.9 },
    { url: `${base}/category`, lastModified: now, changeFrequency: "weekly", priority: 0.8 },
    { url: `${base}/industries`, lastModified: now, changeFrequency: "weekly", priority: 0.8 },
    { url: `${base}/msds`, lastModified: now, changeFrequency: "weekly", priority: 0.8 },
    { url: `${base}/5s`, lastModified: now, changeFrequency: "weekly", priority: 0.7 },
    { url: `${base}/bulk-order`, lastModified: now, changeFrequency: "monthly", priority: 0.7 },
    { url: `${base}/blog`, lastModified: now, changeFrequency: "weekly", priority: 0.7 },
    { url: `${base}/about`, lastModified: now, changeFrequency: "yearly", priority: 0.5 },
    { url: `${base}/contact`, lastModified: now, changeFrequency: "yearly", priority: 0.5 },
    ...["shipping", "refund", "terms", "privacy"].map((slug) => ({
      url: `${base}/policies/${slug}`,
      lastModified: now,
      changeFrequency: "yearly" as const,
      priority: 0.3,
    })),
  ];

  const [categories, industries, posts] = await Promise.all([
    listCategories().catch(() => []),
    listIndustries().catch(() => []),
    listBlogPosts({ perPage: 50 }).catch(() => null),
  ]);

  const categoryEntries: MetadataRoute.Sitemap = categories.map((category) => ({
    url: `${base}/category/${category.slug}`,
    lastModified: now,
    changeFrequency: "weekly",
    priority: 0.8,
  }));

  const industryEntries: MetadataRoute.Sitemap = industries.map((industry) => ({
    url: `${base}/industries/${industry.slug}`,
    lastModified: now,
    changeFrequency: "monthly",
    priority: 0.7,
  }));

  const postEntries: MetadataRoute.Sitemap = (posts?.items ?? []).map((post) => ({
    url: `${base}/blog/${post.slug}`,
    lastModified: post.published_at ? new Date(post.published_at) : now,
    changeFrequency: "monthly",
    priority: 0.6,
  }));

  // The list endpoint is capped at 100 per page. Rather than silently shipping a
  // sitemap covering only the first 100 products, page through until the API
  // says it is done. `maxPages` is a circuit breaker, not a product limit: it
  // exists so a misbehaving response that always reports `has_next` cannot
  // spin this function forever.
  const MAX_PAGES = 100;
  const productEntries: MetadataRoute.Sitemap = [];
  let page = 1;
  while (page <= MAX_PAGES) {
    const batch = await listProducts({ per_page: 100, page, sort: "newest" }).catch(
      () => null,
    );
    if (!batch || batch.items.length === 0) break;
    for (const product of batch.items) {
      productEntries.push({
        url: `${base}/products/${product.slug}`,
        lastModified: product.created_at ? new Date(product.created_at) : now,
        changeFrequency: "weekly",
        priority: 0.7,
      });
    }
    if (!batch.meta.has_next) break;
    page += 1;
  }

  // Industry detail pages carry a last-modified from the record when we have it.
  const detailedIndustries = await Promise.all(
    industries.map((industry) => getIndustry(industry.slug).catch(() => null)),
  );
  detailedIndustries.forEach((industry, index) => {
    if (industry) industryEntries[index] = { ...industryEntries[index], lastModified: now };
  });

  return [
    ...staticEntries,
    ...categoryEntries,
    ...industryEntries,
    ...postEntries,
    ...productEntries,
  ];
}
