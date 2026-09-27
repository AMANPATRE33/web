import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import {
  Check,
  FileWarning,
  Package,
  RotateCcw,
  Truck,
} from "lucide-react";

import { Breadcrumbs, Rating, Sku, StockBadge } from "@/components/catalog/primitives";
import { RelatedCard } from "@/components/catalog/RelatedCard";
import { ProductGallery } from "@/components/product/ProductGallery";
import { VariantSelector } from "@/components/product/VariantSelector";
import { Section } from "@/components/ui";
import { getProduct, getRelatedProducts } from "@/lib/api/catalog";
import { ApiError } from "@/lib/api/client";
import { env } from "@/lib/env";
import { hasRealRating } from "@/lib/money";


// Rendered per request. Prices, stock and availability must never be baked
// into a build: a stale static page would sell a variant that has since sold
// out, at a price the catalogue has since changed.
export const dynamic = "force-dynamic";

/**
 * Product detail.
 *
 * The right-hand column is client-rendered because the Material x Size selector
 * is interactive; everything above and below it is server-rendered from a
 * single `getProduct` call. There is no second fetch for the variant matrix -
 * `product.variants` and `product.options` already carry everything the selector
 * needs, which is why the API returns them.
 *
 * Structured data: Product + BreadcrumbList. The `offers` block uses the
 * cheapest *available* variant as its price, and enumerates the full variant
 * set as separate offers, which is what Google expects for a product with a
 * size matrix.
 */

/**
 * Metadata doubles as the 404 gate.
 *
 * Calling `notFound()` from `generateMetadata` rather than only from the page
 * body is what produces a real 404 *status*. By the time the page component
 * runs, the async root layout has already started streaming the shell, the
 * status line is committed to 200, and `notFound()` can only swap the body -
 * producing a soft 404. Metadata resolves before the body is streamed, so a
 * missing product is a genuine 404 and the crawler sees it.
 */
export async function generateMetadata({
  params,
}: {
  params: Promise<{ slug: string }>;
}): Promise<Metadata> {
  const { slug } = await params;
  try {
    const product = await getProduct(slug);
    const description =
      product.seo_description ??
      product.short_description ??
      `${product.title} safety signage from Safety Poster Prints. Available in ${product.options.length || 1} material/size options.`;

    return {
      title: product.seo_title ?? product.title,
      description,
      alternates: { canonical: `/products/${product.slug}` },
      openGraph: {
        type: "website",
        title: product.title,
        description,
        url: `${env.siteUrl}/products/${product.slug}`,
        images: product.images?.[0]
          ? [{ url: product.images[0].url, alt: product.images[0].alt_text ?? product.title }]
          : undefined,
      },
      twitter: {
        card: "summary_large_image",
        title: product.title,
        description,
        images: product.images?.[0] ? [product.images[0].url] : undefined,
      },
    };
  } catch (error) {
    if (error instanceof ApiError && error.isNotFound) notFound();
    throw error;
  }
}

export default async function ProductPage({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params;

  let product;
  try {
    product = await getProduct(slug);
  } catch (error) {
    if (error instanceof ApiError && error.isNotFound) notFound();
    throw error;
  }

  const related = await getRelatedProducts(slug, 4).catch(() => []);

  const inStockVariants = product.variants.filter((variant) => variant.in_stock);
  const cheapest = inStockVariants.reduce<(typeof inStockVariants)[number] | null>(
    (lowest, variant) =>
      lowest === null || variant.price.amount < lowest.price.amount ? variant : lowest,
    null,
  );
  const offerPrice = cheapest?.price ?? product.price;

  const jsonLd = {
    "@context": "https://schema.org",
    "@type": "Product",
    name: product.title,
    description: product.short_description ?? product.description?.slice(0, 500),
    sku: product.sku,
    ...(product.brand ? { brand: { "@type": "Brand", name: product.brand } } : {}),
    image: product.images.map((image) =>
      image.url.startsWith("http") ? image.url : `${env.siteUrl}${image.url}`,
    ),
    category: product.category?.name,
    ...(hasRealRating(product.rating_count)
      ? {
          aggregateRating: {
            "@type": "AggregateRating",
            ratingValue: product.rating_average.toFixed(1),
            reviewCount: product.rating_count,
          },
        }
      : {}),
    offers: {
      "@type": "AggregateOffer",
      priceCurrency: offerPrice.currency,
      lowPrice: offerPrice.amount / 100,
      highPrice:
        inStockVariants.length > 0
          ? Math.max(...inStockVariants.map((v) => v.price.amount)) / 100
          : offerPrice.amount / 100,
      offerCount: product.variants.length,
      availability: inStockVariants.length > 0
        ? "https://schema.org/InStock"
        : "https://schema.org/OutOfStock",
      seller: { "@type": "Organization", name: "Safety Poster Prints" },
      offers: product.variants.map((variant) => ({
        "@type": "Offer",
        sku: variant.sku,
        name: variant.title,
        price: variant.price.amount / 100,
        priceCurrency: variant.price.currency,
        availability: variant.in_stock
          ? "https://schema.org/InStock"
          : "https://schema.org/OutOfStock",
        url: `${env.siteUrl}/products/${product.slug}`,
      })),
    },
  };

  const breadcrumbJsonLd = {
    "@context": "https://schema.org",
    "@type": "BreadcrumbList",
    itemListElement: [
      { "@type": "ListItem", position: 1, name: "Home", item: env.siteUrl },
      { "@type": "ListItem", position: 2, name: "Shop", item: `${env.siteUrl}/shop` },
      {
        "@type": "ListItem",
        position: 3,
        name: product.category.name,
        item: `${env.siteUrl}/category/${product.category.slug}`,
      },
      { "@type": "ListItem", position: 4, name: product.title },
    ],
  };

  const specs = Object.entries(product.specs ?? {});

  return (
    <Section className="pb-16">
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: JSON.stringify(jsonLd) }}
      />
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: JSON.stringify(breadcrumbJsonLd) }}
      />

      <div className="container-page">
        <Breadcrumbs
          items={[
            { name: "Home", href: "/" },
            { name: "Shop", href: "/shop" },
            { name: product.category.name, href: `/category/${product.category.slug}` },
            { name: product.title },
          ]}
          className="mb-6"
        />

        <div className="grid gap-8 lg:grid-cols-2 lg:gap-12">
          <ProductGallery images={product.images ?? []} title={product.title} />

          <div>
            <p className="eyebrow">{product.category.name}</p>
            <h1 className="mt-2 text-2xl leading-tight sm:text-3xl">{product.title}</h1>

            {product.subtitle ? (
              <p className="mt-2 text-[15px] text-ink-600">{product.subtitle}</p>
            ) : null}

            <div className="mt-3 flex flex-wrap items-center gap-3">
              <Sku value={product.sku} />
              <StockBadge status={product.stock_status} />
              {hasRealRating(product.rating_count) ? (
                <Rating average={product.rating_average} count={product.rating_count} />
              ) : null}
            </div>

            {product.short_description ? (
              <p className="mt-5 text-[15px] leading-relaxed text-ink-700">
                {product.short_description}
              </p>
            ) : null}

            {/* --- the variant matrix --- */}
            <div className="mt-7">
              <VariantSelector product={product} />
            </div>

            {/* --- bulk quote entry point --- */}
            <div className="mt-6 border border-ink-200 bg-ink-50 p-4">
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div>
                  <p className="text-[14px] font-semibold text-ink-950">
                    Ordering for a site or a project?
                  </p>
                  <p className="mt-1 text-[13px] leading-relaxed text-ink-600">
                    Send us your board list and quantities. We will quote freight and volume
                    pricing properly.
                  </p>
                </div>
                <Link
                  href={`/bulk-order?product=${encodeURIComponent(product.slug)}`}
                  className="inline-flex h-10 shrink-0 items-center justify-center rounded-xs border border-ink-900 bg-white px-4 text-[13px] font-semibold text-ink-900 transition-colors hover:bg-ink-100"
                >
                  Request a quote
                </Link>
              </div>
            </div>

            {/* --- logistics --- */}
            <ul className="mt-6 grid gap-3 sm:grid-cols-3">
              <Logistic
                icon={<Truck aria-hidden="true" />}
                title="Delivered across India"
                body="Freight confirmed at checkout or on the quotation."
              />
              <Logistic
                icon={<RotateCcw aria-hidden="true" />}
                title="Returns"
                body="Unused, undamaged boards can be returned. Custom-printed pieces are final sale."
              />
              <Logistic
                icon={<Package aria-hidden="true" />}
                title="Made to order"
                body="Boards are printed for your selected material and size, then packed for transport."
              />
            </ul>
          </div>
        </div>

        {/* --- description + specifications --- */}
        <div className="mt-14 grid gap-10 border-t border-ink-200 pt-10 lg:grid-cols-[1fr_360px]">
          <div className="space-y-8">
            <section>
              <h2 className="text-lg">Description</h2>
              <div className="mt-3 space-y-3 text-[15px] leading-relaxed text-ink-700">
                {(product.description ?? "")
                  .split("\n")
                  .filter((line) => line.trim().length > 0)
                  .map((line, index) => (
                    <p key={index}>{line}</p>
                  ))}
              </div>
            </section>

            {product.tags?.length > 0 ? (
              <section>
                <h2 className="text-lg">Applications</h2>
                <p className="mt-1.5 text-[13px] text-ink-500">
                  Where this board is typically installed, taken from the catalogue tags.
                </p>
                <ul className="mt-3 grid gap-2 sm:grid-cols-2">
                  {product.tags.map((tag) => (
                    <li key={tag} className="flex items-start gap-2.5 text-[14px] text-ink-700">
                      <Check
                        aria-hidden="true"
                        className="mt-0.5 size-4 shrink-0 text-safe-600"
                        strokeWidth={2.5}
                      />
                      {tag}
                    </li>
                  ))}
                </ul>
              </section>
            ) : null}

            {/*
              Reviews.
              The reviews API does not exist yet and the live site publishes no
              reviews, so there is nothing to show. An explicit "no reviews yet"
              is the honest state; a quote from an invented customer is not an
              option.
            */}
            <section>
              <h2 className="text-lg">Customer reviews</h2>
              <div className="mt-3 flex items-start gap-3 border border-dashed border-ink-300 bg-ink-50 p-4">
                <FileWarning aria-hidden="true" className="mt-0.5 size-5 shrink-0 text-ink-400" />
                <div>
                  <p className="text-[14px] font-medium text-ink-800">
                    No reviews published for this product yet.
                  </p>
                  <p className="mt-1 text-[13px] leading-relaxed text-ink-600">
                    We would rather show nothing than show something we cannot verify. If you have
                    bought this board, tell us how it performed.
                  </p>
                </div>
              </div>
            </section>
          </div>

          <aside className="space-y-6">
            {specs.length > 0 ? (
              <div>
                <h2 className="text-lg">Specifications</h2>
                <dl className="mt-3 divide-y divide-ink-200 border-y border-ink-200">
                  {specs.map(([key, value]) => (
                    <div key={key} className="grid grid-cols-[110px_1fr] gap-3 py-2.5">
                      <dt className="text-[12px] font-semibold uppercase tracking-wide text-ink-500">
                        {key}
                      </dt>
                      <dd className="text-[13px] text-ink-900">{value}</dd>
                    </div>
                  ))}
                </dl>
              </div>
            ) : null}

            <div className="border border-ink-200 bg-ink-50 p-4">
              <h2 className="text-[14px] font-semibold text-ink-950">Materials available</h2>
              <ul className="mt-2.5 space-y-1.5">
                {(product.options ?? [])
                  .filter((option) => option.name === "Material")
                  .flatMap((option) => option.values)
                  .map((value) => (
                    <li
                      key={value}
                      className="font-mono text-[12px] uppercase tracking-wide text-ink-700"
                    >
                      {value}
                    </li>
                  ))}
              </ul>
              <p className="mt-3 text-[12px] leading-relaxed text-ink-500">
                Not all materials are made in all sizes. The selector above shows only the
                combinations we actually produce.
              </p>
            </div>

            <div className="border border-ink-200 p-4">
              <h2 className="text-[14px] font-semibold text-ink-950">Shipping</h2>
              <p className="mt-2 text-[13px] leading-relaxed text-ink-600">
                Boards ship panelled and corner-guarded. Freight depends on quantity and
                destination, and is confirmed before your order is charged.
              </p>
              <Link
                href="/policies/shipping"
                className="mt-2 inline-block text-[13px] font-semibold text-ink-900 underline underline-offset-4"
              >
                Read the shipping policy
              </Link>
            </div>
          </aside>
        </div>

        {/* --- related --- */}
        {related.length > 0 ? (
          <section className="mt-14 border-t border-ink-200 pt-10">
            <h2 className="mb-6 text-lg">Related products</h2>
            <div className="grid grid-cols-2 gap-3 sm:gap-4 md:grid-cols-4">
              {related.map((item) => (
                <RelatedCard key={item.id} product={item} />
              ))}
            </div>
          </section>
        ) : null}
      </div>
    </Section>
  );
}

function Logistic({
  icon,
  title,
  body,
}: {
  icon: React.ReactNode;
  title: string;
  body: string;
}) {
  return (
    <li className="border-t-2 border-signal-400 pt-3">
      <p className="flex items-center gap-2 text-[13px] font-semibold text-ink-950">
        <span className="text-ink-400 [&_svg]:size-4">{icon}</span>
        {title}
      </p>
      <p className="mt-1.5 text-[12px] leading-relaxed text-ink-600">{body}</p>
    </li>
  );
}
