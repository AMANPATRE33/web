/**
 * Image URL resolution.
 *
 * Image `url` values arrive in two shapes and the storefront must handle both
 * without special-casing call sites:
 *
 *   - a **root-relative path** like `/seed/electrical-safety/SPP-ELS-001.svg`.
 *     That is what the seed writes into `product_images.url`, and the files
 *     live in this app's own `public/` directory, so the path resolves against
 *     the Next.js origin and needs no prefix.
 *   - an **absolute URL**, which is what Supabase Storage will return once the
 *     real photography is migrated (`scripts/import_products.py`).
 *
 * Anything else is passed through untouched rather than guessed at, so a bad
 * value surfaces as one broken image instead of a silently wrong host.
 *
 * Nothing here references the old Wix CDN. The reference site is a content
 * source, not an asset host.
 */

import { env } from "./env";

export function resolveImageUrl(url: string | null | undefined): string | null {
  if (!url) return null;
  const trimmed = url.trim();
  if (trimmed.length === 0) return null;
  if (/^https?:\/\//i.test(trimmed)) return trimmed;
  // Checked *before* the root-relative case: "//host/path" also starts with a
  // slash, and treating it as a local path would 404 every protocol-relative URL.
  if (/^\/\//.test(trimmed)) return `https:${trimmed}`;
  if (trimmed.startsWith("/")) return trimmed;
  // A bare host or path: assume the storage origin rather than guessing a path
  // on our own domain.
  return `${env.apiUrl.replace(/\/$/, "")}/${trimmed.replace(/^\//, "")}`;
}

/**
 * Whether an image can go through the Next.js optimiser.
 *
 * SVG is not a raster format. `next/image` refuses to optimise it unless
 * `dangerouslyAllowSVG` is enabled, which we deliberately do not enable because
 * it also requires `contentDispositionType: attachment` and a restrictive CSP to
 * stay safe. Passing `unoptimized` renders the file directly through the
 * `<Image>` component instead, which keeps width/height, lazy loading and the
 * `alt` handling.
 */
export function isVector(url: string): boolean {
  return /\.svg(\?|#|$)/i.test(url);
}

export function altText(
  explicit: string | null | undefined,
  productTitle: string,
  suffix?: string,
): string {
  if (explicit && explicit.trim()) return explicit;
  return suffix
    ? `${productTitle} - ${suffix}`
    : `${productTitle} safety signage`;
}
