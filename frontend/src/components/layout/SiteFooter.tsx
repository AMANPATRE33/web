import Link from "next/link";
import {
  Factory,
  FileWarning,
  Flame,
  HardHat,
  Mail,
  MapPin,
  Phone,
  Ruler,
  ShieldCheck,
} from "lucide-react";

import type { Category } from "@/lib/api/types";
import { business, isPending } from "@/lib/env";

/**
 * Footer.
 *
 * Three things are deliberately absent: invented statistics, a customer count
 * and testimonials. The live site publishes none, so neither does this. The
 * "why choose us" block below paraphrases the business's own four stated
 * pillars, which are verified.
 */
export function SiteFooter({ categories }: { categories: Category[] }) {
  // Split across the two link columns purely for layout. The taxonomy is flat -
  // this is not a hierarchy, and the split is a function of how many
  // categories exist rather than of any editorial grouping.
  const half = Math.ceil(categories.length / 2);
  const firstHalf = categories.slice(0, half);
  const secondHalf = categories.slice(half);

  return (
    <footer className="mt-auto border-t border-ink-200 bg-ink-50">
      {/* --- value props: the business's own four pillars, reworded --- */}
      <div className="border-b border-ink-200">
        <div className="container-page grid gap-6 py-10 sm:grid-cols-2 lg:grid-cols-4">
          <ValueProp
            icon={<ShieldCheck aria-hidden="true" />}
            title="Compliance-ready print"
            body="Boards that follow the signage conventions your auditor already recognises."
          />
          <ValueProp
            icon={<Ruler aria-hidden="true" />}
            title="Sized to the wall"
            body="Eight sizes from 8x12 to 48x96, so the board fits the space you actually have."
          />
          <ValueProp
            icon={<HardHat aria-hidden="true" />}
            title="Material for the location"
            body="ACP, foam sheet, autoglow or vinyl - chosen for where the board goes, not just its price."
          />
          <ValueProp
            icon={<Factory aria-hidden="true" />}
            title="Built for volume"
            body="Single boards or site-wide sets. Request a quote and we will price it properly."
          />
        </div>
      </div>

      {/* --- link columns --- */}
      <div className="container-page grid gap-10 py-12 sm:grid-cols-2 lg:grid-cols-5">
        <div className="lg:col-span-2">
          <p className="text-[15px] font-extrabold uppercase tracking-[-0.02em] text-ink-950">
            Safety Poster Prints
          </p>
          <p className="mt-3 max-w-sm text-sm leading-relaxed text-ink-600">
            {business.description}
          </p>

          <address className="mt-5 space-y-2.5 not-italic text-sm text-ink-700">
            <p className="flex items-start gap-2.5">
              <MapPin
                aria-hidden="true"
                className="mt-0.5 size-4 shrink-0 text-ink-400"
              />
              <span>
                {business.address}
                {isPending(business.mapsUrl) ? null : (
                  <Link
                    href={business.mapsUrl!}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="mt-1 block text-[13px] font-semibold text-ink-900 underline underline-offset-4"
                  >
                    View on map
                  </Link>
                )}
              </span>
            </p>
            <p className="flex items-center gap-2.5">
              <Phone aria-hidden="true" className="size-4 shrink-0 text-ink-400" />
              <a href={business.phoneHref} className="hover:underline">
                {business.phone}
              </a>
            </p>
            <p className="flex items-center gap-2.5">
              <Mail aria-hidden="true" className="size-4 shrink-0 text-ink-400" />
              <a href={`mailto:${business.email}`} className="hover:underline">
                {business.email}
              </a>
            </p>
            {isPending(business.businessHours) ? (
              <p className="text-[13px] italic text-ink-400">
                Business hours not yet published
              </p>
            ) : (
              <p className="text-ink-600">{business.businessHours}</p>
            )}
            {isPending(business.gstin) ? (
              <p className="text-[13px] italic text-ink-400">GSTIN not yet published</p>
            ) : (
              <p className="font-mono text-[13px] text-ink-600">GSTIN {business.gstin}</p>
            )}
          </address>
        </div>

        <FooterColumn title="Shop">
          <FooterLink href="/shop">All products</FooterLink>
          <FooterLink href="/shop?sort=price_asc">Price: low to high</FooterLink>
          <FooterLink href="/shop?on_sale=true">On sale</FooterLink>
          <FooterLink href="/shop?in_stock=true">In stock</FooterLink>
          <FooterLink href="/bulk-order">Bulk order quote</FooterLink>
        </FooterColumn>

        <FooterColumn title="Categories A&ndash;M">
          {firstHalf.map((category) => (
            <FooterLink key={category.slug} href={`/category/${category.slug}`}>
              {category.name}
            </FooterLink>
          ))}
        </FooterColumn>

        <FooterColumn title="Categories N&ndash;Z">
          {secondHalf.map((category) => (
            <FooterLink key={category.slug} href={`/category/${category.slug}`}>
              {category.name}
            </FooterLink>
          ))}
          {categories.length > 6 ? (
            <FooterLink href="/category" emphasis>
              View all {categories.length}
            </FooterLink>
          ) : null}
        </FooterColumn>

        <FooterColumn title="Resources">
          <FooterLink href="/industries">
            <Factory aria-hidden="true" className="size-3.5" /> Industries
          </FooterLink>
          <FooterLink href="/msds">
            <FileWarning aria-hidden="true" className="size-3.5" /> MSDS boards
          </FooterLink>
          <FooterLink href="/5s">5S methodology</FooterLink>
          <FooterLink href="/blog">Knowledge centre</FooterLink>
          <FooterLink href="/about">About us</FooterLink>
          <FooterLink href="/contact">
            <Flame aria-hidden="true" className="size-3.5" /> Contact
          </FooterLink>
        </FooterColumn>
      </div>

      <div className="border-t border-ink-200">
        <div className="container-page flex flex-col gap-3 py-5 text-[13px] text-ink-500 sm:flex-row sm:items-center sm:justify-between">
          <p>
            &copy; {new Date().getFullYear()} {business.name}. All rights reserved.
          </p>
          <nav aria-label="Legal" className="flex flex-wrap gap-x-5 gap-y-1">
            <Link href="/policies/terms" className="hover:text-ink-900">
              Terms
            </Link>
            <Link href="/policies/privacy" className="hover:text-ink-900">
              Privacy
            </Link>
            <Link href="/policies/refund" className="hover:text-ink-900">
              Refund
            </Link>
            <Link href="/policies/shipping" className="hover:text-ink-900">
              Shipping
            </Link>
          </nav>
        </div>
      </div>
    </footer>
  );
}

function ValueProp({
  icon,
  title,
  body,
}: {
  icon: React.ReactNode;
  title: string;
  body: string;
}) {
  return (
    <div className="flex gap-3">
      <span className="mt-0.5 shrink-0 text-ink-400 [&_svg]:size-5">{icon}</span>
      <div>
        <p className="text-sm font-semibold text-ink-900">{title}</p>
        <p className="mt-1 text-[13px] leading-relaxed text-ink-600">{body}</p>
      </div>
    </div>
  );
}

function FooterColumn({
  title,
  children,
}: {
  title: string;
  children: React.ReactNode;
}) {
  return (
    <div>
      <p className="eyebrow mb-3">{title}</p>
      <ul className="space-y-2">{children}</ul>
    </div>
  );
}

function FooterLink({
  href,
  children,
  emphasis,
}: {
  href: string;
  children: React.ReactNode;
  emphasis?: boolean;
}) {
  return (
    <li>
      <Link
        href={href}
        // Same reasoning as the header's category rail: the footer carries
        // dozens of links on every page. Prefetching all of them is what turned
        // a 1.2s page into 98 network requests.
        prefetch={false}
        className={
          emphasis
            ? "inline-flex items-center gap-1.5 text-[13px] font-semibold text-ink-900 underline underline-offset-4"
            : "inline-flex items-center gap-1.5 text-sm text-ink-600 hover:text-ink-950 hover:underline"
        }
      >
        {children}
      </Link>
    </li>
  );
}
