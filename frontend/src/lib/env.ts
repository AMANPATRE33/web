/**
 * Runtime configuration.
 *
 * ## Why the variables are read as literals
 *
 * Next.js inlines `process.env.NEXT_PUBLIC_*` into the client bundle at build
 * time, but only for **statically analysable member access** -
 * `process.env.NEXT_PUBLIC_API_URL`. A dynamic lookup such as
 * `process.env[name]` is not analysable, so it survives into the browser bundle
 * as a real `process.env` lookup, evaluates to `undefined`, and every client
 * component that imports this module throws at module-evaluation time.
 *
 * That failure is invisible to `next build` and to server-side typecheck: the
 * server has the real environment. It only appears in a real browser, which is
 * why the Playwright sweep in `qa/` exists.
 *
 * So: every variable below is read as a literal, and the "is it configured?"
 * check runs on the inlined value rather than on a lookup.
 */

const RAW_API_URL = process.env.NEXT_PUBLIC_API_URL;
const RAW_SITE_URL = process.env.NEXT_PUBLIC_SITE_URL;

/**
 * Resolves a value that Next has already inlined, falling back in development.
 *
 * In production a missing value is a hard error. Shipping a storefront pointed
 * at localhost looks broken in a way that is very hard to diagnose from a bug
 * report, so it fails loudly at boot instead.
 */
function resolve(raw: string | undefined, name: string, developmentFallback: string): string {
  const value = typeof raw === "string" && raw.length > 0 ? raw : undefined;
  if (value) return value.replace(/\/$/, "");
  if (process.env.NODE_ENV === "production") {
    throw new Error(
      `Missing required environment variable ${name}. ` +
        `Copy .env.example to .env.local and fill it in.`,
    );
  }
  return developmentFallback;
}

const apiUrl = resolve(RAW_API_URL, "NEXT_PUBLIC_API_URL", "http://localhost:8000");
const siteUrl = resolve(RAW_SITE_URL, "NEXT_PUBLIC_SITE_URL", "http://localhost:3000");

export const env = {
  apiUrl,
  siteUrl,
  siteName: process.env.NEXT_PUBLIC_SITE_NAME || "Safety Poster Prints",
  supabaseUrl: process.env.NEXT_PUBLIC_SUPABASE_URL || "",
  supabasePublishableKey: process.env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY || "",
  razorpayKeyId: process.env.NEXT_PUBLIC_RAZORPAY_KEY_ID || "",
} as const;

/**
 * Verified business facts.
 *
 * Sourced from the public website on 2026-09-27 - see
 * `docs/REFERENCE_SITE_ANALYSIS.md`. Nothing here is invented, and nothing the
 * business has not published is filled in.
 */
export const business = {
  name: "Safety Poster Prints",
  tagline: "Industrial Safety Signage & Posters — Delivered Across India",
  description:
    "Professional safety posters, sign boards and workplace communication " +
    "products for industries, offices and facilities across India.",
  address:
    "GF-40, 41, 42, Real Square, Ankleshwar - Valia Rd, opp. Sanatan School, " +
    "GIDC, Ankleshwar, Kosamdi, Gujarat 393002",
  addressLocality: "Ankleshwar",
  addressRegion: "Gujarat",
  postalCode: "393002",
  countryCode: "IN",
  email: "safetyposterprint@gmail.com",
  phone: "+91 83200 50573",
  phoneHref: "tel:+918320050573",
  instagram: "https://www.instagram.com/safetypostersprint",
  whatsapp: "https://wa.me/918320050573",

  /**
   * Not published by the business. Rendered as an explicit pending state.
   * See `docs/CONTENT_PENDING.md`.
   */
  gstin: null as string | null,
  businessHours: null as string | null,
  mapsUrl: null as string | null,
  foundedYear: null as number | null,
  customerCount: null as number | null,
  reviewCount: null as number | null,
} as const;

/** True when a fact the UI wants to show has not been supplied yet. */
export function isPending(value: unknown): boolean {
  return value === null || value === undefined || value === "";
}
