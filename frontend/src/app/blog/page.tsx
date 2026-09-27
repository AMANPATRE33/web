import type { Metadata } from "next";
import Link from "next/link";
import { BookOpen } from "lucide-react";

import { Breadcrumbs } from "@/components/catalog/primitives";
import { ProductImage } from "@/components/catalog/ProductImage";
import { Pagination } from "@/components/catalog/ProductGrid";
import { Button, EmptyState, Section } from "@/components/ui";
import { listBlogPosts } from "@/lib/api/content";
import { env } from "@/lib/env";

// Rendered per request. Prices, stock and availability must never be baked
// into a build: a stale static page would sell a variant that has since sold
// out, at a price the catalogue has since changed.
export const dynamic = "force-dynamic";

export const metadata: Metadata = {
  title: "Knowledge centre - safety signage guides",
  description:
    "Practical guides on safety signage: choosing materials, size standards, GHS hazard communication, 5S implementation and compliance deadlines.",
  alternates: { canonical: "/blog" },
};

function formatDate(iso: string | null): string {
  if (!iso) return "";
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return "";
  return new Intl.DateTimeFormat("en-IN", {
    day: "numeric",
    month: "short",
    year: "numeric",
    timeZone: "Asia/Kolkata",
  }).format(date);
}

export default async function BlogIndexPage({
  searchParams,
}: {
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}) {
  const raw = await searchParams;
  const page = Math.max(1, Number.parseInt(String(raw.page ?? "1"), 10) || 1);
  const perPage = 12;

  const posts = await listBlogPosts({ page, perPage }).catch(() => null);
  const pageHref = (target: number) =>
    `/blog${target > 1 ? `?page=${target}` : ""}`;

  const jsonLd = posts && posts.items.length > 0
    ? {
        "@context": "https://schema.org",
        "@type": "Blog",
        name: "Safety Poster Prints knowledge centre",
        url: `${env.siteUrl}/blog`,
        blogPost: posts.items.map((post) => ({
          "@type": "BlogPosting",
          headline: post.title,
          description: post.excerpt,
          url: `${env.siteUrl}/blog/${post.slug}`,
          datePublished: post.published_at ?? undefined,
          ...(post.cover_image_url
            ? {
                image: post.cover_image_url.startsWith("http")
                  ? post.cover_image_url
                  : `${env.siteUrl}${post.cover_image_url}`,
              }
            : {}),
          publisher: { "@type": "Organization", name: "Safety Poster Prints" },
        })),
      }
    : null;

  return (
    <Section className="pb-16">
      {jsonLd ? (
        <script
          type="application/ld+json"
          dangerouslySetInnerHTML={{ __html: JSON.stringify(jsonLd) }}
        />
      ) : null}

      <div className="container-page">
        <Breadcrumbs items={[{ name: "Home", href: "/" }, { name: "Blog" }]} className="mb-4" />
        <header className="mb-8">
          <p className="eyebrow">Knowledge centre</p>
          <h1 className="mt-2 text-2xl sm:text-3xl">Safety signage guides</h1>
          <p className="mt-3 max-w-2xl text-[15px] leading-relaxed text-ink-600">
            Practical notes on choosing signage: which material belongs where, which size an
            auditor will accept, and what changes when the standards move. Written for people who
            have to specify and maintain the boards, not for a search engine.
          </p>
        </header>

        {!posts ? (
          <EmptyState
            icon={<BookOpen aria-hidden="true" className="size-10" />}
            title="We couldn't load the guides"
            description="The content service did not respond. Please try again shortly."
            action={
              <Button variant="outline" asChild>
                <Link href="/blog">Retry</Link>
              </Button>
            }
          />
        ) : posts.items.length === 0 ? (
          <EmptyState
            icon={<BookOpen aria-hidden="true" className="size-10" />}
            title="No guides published yet"
            description="Guides are on the way. In the meantime, the catalogue and the material guides on each product page will answer most questions."
            action={
              <Button variant="primary" asChild>
                <Link href="/shop">Browse all products</Link>
              </Button>
            }
          />
        ) : (
          <>
            <ul className="grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
              {posts.items.map((post) => (
                <li key={post.id}>
                  <article className="group flex h-full flex-col border border-ink-200 bg-white transition-[border-color,box-shadow] hover:border-ink-900 hover:shadow-[0_2px_12px_rgba(11,13,16,0.08)]">
                    {post.cover_image_url ? (
                      <Link href={`/blog/${post.slug}`} tabIndex={-1} aria-hidden="true">
                        <ProductImage
                          src={post.cover_image_url}
                          alt={post.cover_image_alt ?? ""}
                          sizes="(min-width: 1024px) 33vw, (min-width: 640px) 50vw, 100vw"
                          className="aspect-[3/2] w-full border-b border-ink-100 p-0"
                          imageClassName="object-cover"
                        />
                      </Link>
                    ) : null}
                    <div className="flex flex-1 flex-col p-5">
                      <p className="flex flex-wrap items-center gap-x-3 gap-y-1 text-[11px] uppercase tracking-[0.06em] text-ink-500">
                        <time dateTime={post.published_at ?? undefined}>
                          {formatDate(post.published_at)}
                        </time>
                        {post.reading_minutes ? (
                          <>
                            <span aria-hidden="true">·</span>
                            <span className="tabular">{post.reading_minutes} min read</span>
                          </>
                        ) : null}
                      </p>
                      <h2 className="mt-2 text-[16px] leading-snug font-semibold text-ink-950">
                        <Link href={`/blog/${post.slug}`} className="hover:underline">
                          {post.title}
                        </Link>
                      </h2>
                      <p className="mt-2 line-clamp-3 text-[13px] leading-relaxed text-ink-600">
                        {post.excerpt}
                      </p>
                    </div>
                  </article>
                </li>
              ))}
            </ul>
            <Pagination meta={posts.meta} buildHref={pageHref} />
          </>
        )}
      </div>
    </Section>
  );
}
