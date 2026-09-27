import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";

import { Breadcrumbs } from "@/components/catalog/primitives";
import { ProductGrid } from "@/components/catalog/ProductGrid";
import { Markdown } from "@/components/content/Markdown";
import { Button, Section } from "@/components/ui";
import { ApiError } from "@/lib/api/client";
import { getBlogPost, listBlogPosts } from "@/lib/api/content";
import { listProducts } from "@/lib/api/catalog";
import { business, env } from "@/lib/env";

// Rendered per request. Prices, stock and availability must never be baked
// into a build: a stale static page would sell a variant that has since sold
// out, at a price the catalogue has since changed.
export const dynamic = "force-dynamic";

export async function generateStaticParams() {
  try {
    const posts = await listBlogPosts({ perPage: 50 });
    return posts.items.map((post) => ({ slug: post.slug }));
  } catch {
    return [];
  }
}

export async function generateMetadata({
  params,
}: {
  params: Promise<{ slug: string }>;
}): Promise<Metadata> {
  const { slug } = await params;
  try {
    const post = await getBlogPost(slug);
    const description = post.seo_description ?? post.excerpt;
    return {
      title: post.seo_title ?? post.title,
      description,
      alternates: { canonical: `/blog/${post.slug}` },
      openGraph: {
        type: "article",
        title: post.title,
        description,
        url: `${env.siteUrl}/blog/${post.slug}`,
        publishedTime: post.published_at ?? undefined,
        images: post.cover_image_url
          ? [{ url: post.cover_image_url, alt: post.cover_image_alt ?? post.title }]
          : undefined,
      },
      twitter: {
        card: "summary_large_image",
        title: post.title,
        description,
      },
    };
  } catch (error) {
    // See `products/[slug]/page.tsx`: notFound() from metadata is what sets a
    // real 404 status rather than a soft one.
    if (error instanceof ApiError && error.isNotFound) notFound();
    throw error;
  }
}

function formatDate(iso: string | null): string {
  if (!iso) return "";
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return "";
  return new Intl.DateTimeFormat("en-IN", {
    day: "numeric",
    month: "long",
    year: "numeric",
    timeZone: "Asia/Kolkata",
  }).format(date);
}

export default async function BlogPostPage({
  params,
}: {
  params: Promise<{ slug: string }>;
}) {
  const { slug } = await params;

  let post;
  try {
    post = await getBlogPost(slug);
  } catch (error) {
    if (error instanceof ApiError && error.isNotFound) notFound();
    throw error;
  }

  const relatedProducts = post.related_products.length
    ? (
        await listProducts({
          slug: post.related_products.map((entry) => entry.slug).slice(0, 4),
          per_page: 4,
        }).catch(() => null)
      )?.items ?? []
    : [];

  const articleJsonLd = {
    "@context": "https://schema.org",
    "@type": "BlogPosting",
    headline: post.title,
    description: post.seo_description ?? post.excerpt,
    ...(post.cover_image_url
      ? {
          image: post.cover_image_url.startsWith("http")
            ? post.cover_image_url
            : `${env.siteUrl}${post.cover_image_url}`,
        }
      : {}),
    datePublished: post.published_at ?? undefined,
    dateModified: post.published_at ?? undefined,
    // Only emitted when the post actually has an author. The live site
    // publishes none, so the seed leaves it null and this is omitted rather
    // than filled with the business name as a pretend author.
    ...(post.author_name ? { author: { "@type": "Person", name: post.author_name } } : {}),
    publisher: { "@type": "Organization", name: business.name, url: env.siteUrl },
    mainEntityOfPage: {
      "@type": "WebPage",
      "@id": `${env.siteUrl}/blog/${post.slug}`,
    },
  };

  const breadcrumbJsonLd = {
    "@context": "https://schema.org",
    "@type": "BreadcrumbList",
    itemListElement: [
      { "@type": "ListItem", position: 1, name: "Home", item: env.siteUrl },
      { "@type": "ListItem", position: 2, name: "Blog", item: `${env.siteUrl}/blog` },
      { "@type": "ListItem", position: 3, name: post.title },
    ],
  };

  const faqJsonLd =
    post.faq && post.faq.length > 0
      ? {
          "@context": "https://schema.org",
          "@type": "FAQPage",
          mainEntity: post.faq.map((entry) => ({
            "@type": "Question",
            name: entry.question,
            acceptedAnswer: { "@type": "Answer", text: entry.answer },
          })),
        }
      : null;

  return (
    <Section className="pb-16">
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: JSON.stringify(articleJsonLd) }}
      />
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: JSON.stringify(breadcrumbJsonLd) }}
      />
      {faqJsonLd ? (
        <script
          type="application/ld+json"
          dangerouslySetInnerHTML={{ __html: JSON.stringify(faqJsonLd) }}
        />
      ) : null}

      <div className="container-page">
        <div className="mx-auto max-w-3xl">
          <Breadcrumbs
            items={[
              { name: "Home", href: "/" },
              { name: "Blog", href: "/blog" },
              { name: post.title },
            ]}
            className="mb-6"
          />

          <article>
            <header>
              <p className="flex flex-wrap items-center gap-x-3 gap-y-1 text-[12px] uppercase tracking-[0.06em] text-ink-500">
                {post.published_at ? (
                  <time dateTime={post.published_at}>{formatDate(post.published_at)}</time>
                ) : null}
                {post.reading_minutes ? (
                  <>
                    <span aria-hidden="true">·</span>
                    <span className="tabular">{post.reading_minutes} min read</span>
                  </>
                ) : null}
                {/*
                  No byline. The live site publishes no author, so the seed left
                  `author_name` null rather than inventing one, and rendering a
                  company name as the author would be a fabricated byline.
                */}
              </p>
              <h1 className="mt-3 text-[28px] leading-tight sm:text-4xl">{post.title}</h1>
              <p className="mt-4 text-[17px] leading-relaxed text-ink-600">{post.excerpt}</p>
            </header>

            {post.compliance_deadline ? (
              <p className="mt-6 border-l-2 border-signal-400 bg-signal-50 py-2.5 pl-4 text-[13px] font-medium text-ink-800">
                Compliance deadline referenced: {formatDate(post.compliance_deadline)}
              </p>
            ) : null}

            <div className="mt-8">
              <Markdown source={post.body} />
            </div>
          </article>

          {post.faq && post.faq.length > 0 ? (
            <section className="mt-12 border-t border-ink-200 pt-10">
              <h2 className="text-xl">Frequently asked</h2>
              <dl className="mt-5 space-y-5">
                {post.faq.map((entry) => (
                  <div key={entry.question} className="border-l-2 border-ink-200 pl-4">
                    <dt className="text-[15px] font-semibold text-ink-950">
                      {entry.question}
                    </dt>
                    <dd className="mt-1.5 text-[14px] leading-relaxed text-ink-600">
                      {entry.answer}
                    </dd>
                  </div>
                ))}
              </dl>
            </section>
          ) : null}

          {relatedProducts.length > 0 ? (
            <section className="mt-12 border-t border-ink-200 pt-10">
              <h2 className="mb-6 text-xl">Boards mentioned in this guide</h2>
              <ProductGrid products={relatedProducts} priorityCount={2} />
            </section>
          ) : null}

          <aside className="mt-12 border border-ink-200 bg-ink-50 p-6">
            <h2 className="text-[15px] font-bold text-ink-950">
              Need this signage on your site?
            </h2>
            <p className="mt-2 text-[13px] leading-relaxed text-ink-600">
              Send your board list and quantities. We will quote freight and volume pricing
              properly, and confirm which sizes and materials we can actually make.
            </p>
            <div className="mt-4 flex flex-wrap gap-2">
              <Button variant="primary" asChild>
                <Link href="/bulk-order">Request a bulk quote</Link>
              </Button>
              <Button variant="outline" asChild>
                <Link href="/shop">Browse all products</Link>
              </Button>
            </div>
          </aside>
        </div>
      </div>
    </Section>
  );
}
