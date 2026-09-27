import type { Metadata } from "next";
import { IBM_Plex_Mono, Inter } from "next/font/google";

import { CartProvider } from "@/components/cart/CartProvider";
import { WishlistProvider } from "@/components/wishlist/WishlistProvider";
import { AnnouncementBar } from "@/components/layout/AnnouncementBar";
import { SiteFooter } from "@/components/layout/SiteFooter";
import { SiteHeader } from "@/components/layout/SiteHeader";
import { listCategories } from "@/lib/api/catalog";
import { business, env } from "@/lib/env";

import "./globals.css";

/**
 * Typography.
 *
 * `Inter` for UI text and `IBM Plex Mono` for SKUs, prices, size and material
 * labels. The mono is doing real work rather than decoration: a safety buyer
 * compares "SPP-ELS-006-ECOVINYLSTICKER-12X18" against a quotation, and material
 * and size values are codes that must not be ambiguous. Rendering them in a
 * proportional face invites exactly the misreading that causes a wrong order.
 */
const inter = Inter({
  subsets: ["latin"],
  display: "swap",
  variable: "--font-inter",
});

const plexMono = IBM_Plex_Mono({
  subsets: ["latin"],
  weight: ["400", "500", "600"],
  display: "swap",
  variable: "--font-plex-mono",
});

export const metadata: Metadata = {
  metadataBase: new URL(env.siteUrl),
  title: {
    default: `${business.name} — Industrial Safety Posters, Sign Boards & Signage`,
    template: `%s | ${business.name}`,
  },
  description: business.description,
  applicationName: business.name,
  authors: [{ name: business.name }],
  creator: business.name,
  publisher: business.name,
  keywords: [
    "safety posters",
    "safety signage",
    "industrial signage",
    "MSDS boards",
    "5S posters",
    "sign boards India",
    "workplace safety signage",
  ],
  alternates: { canonical: "/" },
  openGraph: {
    type: "website",
    siteName: business.name,
    locale: "en_IN",
    url: env.siteUrl,
  },
  twitter: {
    card: "summary_large_image",
    title: business.name,
    description: business.description,
  },
  robots: {
    index: true,
    follow: true,
    googleBot: { index: true, follow: true, "max-image-preview": "large" },
  },
  formatDetection: { telephone: true, address: true, email: true },
};

/**
 * Organisation structured data on every page.
 *
 * Only verified fields appear. `taxID` and `openingHours` are absent because the
 * business has not published them - see `docs/CONTENT_PENDING.md`. Emitting a
 * placeholder GSTIN would be worse than emitting nothing, because it would be
 * indexed.
 */
const organisationJsonLd = {
  "@context": "https://schema.org",
  "@type": "Organization",
  name: business.name,
  url: env.siteUrl,
  description: business.description,
  email: business.email,
  telephone: business.phone,
  address: {
    "@type": "PostalAddress",
    streetAddress: "GF-40, 41, 42, Real Square, Ankleshwar - Valia Rd, opp. Sanatan School, GIDC",
    addressLocality: business.addressLocality,
    addressRegion: business.addressRegion,
    postalCode: business.postalCode,
    addressCountry: business.countryCode,
  },
  sameAs: [business.instagram],
};

export default async function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  // Categories come from the database, once, at the layout level, so the header
  // strip and the footer columns cannot drift from the catalogue. If the API is
  // unreachable the storefront still renders: navigation degrades to the static
  // utility links rather than the whole page 500ing.
  let categories: Awaited<ReturnType<typeof listCategories>> = [];
  try {
    categories = await listCategories();
  } catch {
    categories = [];
  }

  const navCategories = categories.map((category) => ({
    name: category.name,
    slug: category.slug,
    count: category.product_count,
  }));

  return (
    <html lang="en-IN" className={`${inter.variable} ${plexMono.variable}`}>
      <body className="flex min-h-dvh flex-col antialiased">
        <script
          type="application/ld+json"
          // Serialised from a literal object with no user input in it.
          dangerouslySetInnerHTML={{ __html: JSON.stringify(organisationJsonLd) }}
        />
        <CartProvider>
          <WishlistProvider>
            <a href="#main" className="skip-link">
              Skip to main content
            </a>
            <AnnouncementBar />
            <SiteHeader categories={navCategories} />
            <main id="main" className="flex-1">
              {children}
            </main>
            <SiteFooter categories={categories} />
          </WishlistProvider>
        </CartProvider>
      </body>
    </html>
  );
}
