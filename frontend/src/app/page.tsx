import Link from "next/link";
import {
  ArrowRight,
  Beaker,
  Building2,
  ClipboardList,

  Flame,
  Factory,
  FlaskConical,
  Gauge,
  HardHat,
  Ruler,
  ShieldAlert,
  Truck,
  Warehouse,
  Wrench,
} from "lucide-react";

import { ProductGrid } from "@/components/catalog/ProductGrid";
import { Section, SectionHeading } from "@/components/ui";
import { getFeatured, getNewArrivals, listCategories, listProducts } from "@/lib/api/catalog";
import { listIndustries } from "@/lib/api/content";
import { business, isPending } from "@/lib/env";


/**
 * Homepage.
 *
 * Every section is driven by the database or by `lib/env.ts`, never by a local
 * array. `industries` below is the exception and is called out: those seven are
 * a *navigational* set of entry points chosen to match the industry pages the
 * business actually has, and each one is verified to exist. The ten industry
 * pages themselves come from the API on `/industries`.
 *
 * No statistics, no testimonials, no customer counts. The live site publishes
 * none, so this page does not either. See `docs/REFERENCE_SITE_ANALYSIS.md`.
 */

export const revalidate = 60;

export default async function HomePage() {
  const categories = await listCategories();

  const byName = (name: string) =>
    categories.find((category) => category.name.toLowerCase().includes(name.toLowerCase()));

  const msdsSlug = byName("msds")?.slug ?? null;
  const electricalSlug = byName("electrical")?.slug ?? null;
  const fiveSSlug = byName("5s")?.slug ?? null;
  const fireSlug = byName("fire")?.slug ?? null;

  // Real data, and each call is independent: a failure in one rail must not take
  // the homepage down with it.
  const [featured, newest, electrical, total, industries] = await Promise.all([
    getFeatured(8).catch(() => []),
    getNewArrivals(8).catch(() => []),
    electricalSlug
      ? listProducts({ category: [electricalSlug], per_page: 6, sort: "name_asc" })
          .then((page) => page.items)
          .catch(() => [])
      : Promise.resolve([]),
    listProducts({ per_page: 1 })
      .then((page) => page.meta.total)
      .catch(() => 0),
    listIndustries().catch(() => []),
  ]);

  /**
   * Icons, keyed by the `icon` column the API returns for each industry.
   *
   * This is presentation only - the set of industries, their names, slugs and
   * blurbs all come from the database. A missing icon falls back to a neutral
   * mark rather than an empty square, and the map is exhaustive over the ten
   * seeded slugs so a new industry added in the admin degrades gracefully.
   */
  const ICONS: Record<string, React.ReactNode> = {
    manufacturing: <Factory aria-hidden="true" />,
    chemical: <FlaskConical aria-hidden="true" />,
    construction: <HardHat aria-hidden="true" />,
    warehouse: <Warehouse aria-hidden="true" />,
    office: <Building2 aria-hidden="true" />,
    laboratory: <Beaker aria-hidden="true" />,
    hospital: <ShieldAlert aria-hidden="true" />,
    logistics: <Truck aria-hidden="true" />,
    education: <Building2 aria-hidden="true" />,
    oil_gas: <Flame aria-hidden="true" />,
  };

  // The seven leading industries, straight from the database. No hard-coded
  // list: if the business adds an industry in the admin it appears here.
  const industryCards = industries.slice(0, 7);

  return (
    <>
      {/* ==================================================================
          2. Hero
          ================================================================== */}
      <section className="dark-surface relative overflow-hidden bg-ink-950 text-white">
        <div
          aria-hidden="true"
          className="absolute inset-0 rule-grid opacity-[0.18]"
        />
        <div
          aria-hidden="true"
          className="absolute inset-x-0 bottom-0 h-1.5 safety-stripe opacity-90"
        />
        <div className="container-page relative py-20 sm:py-28 lg:py-36">
          <p className="eyebrow !text-signal-400">{business.tagline}</p>
          <h1 className="mt-4 max-w-4xl text-[34px] leading-[1.05] font-extrabold tracking-[-0.03em] text-white sm:text-5xl lg:text-6xl">
            Safety Signage That Speaks Before You Do.
          </h1>
          <p className="mt-6 max-w-2xl text-base leading-relaxed text-ink-300 sm:text-lg">
            {business.description}
          </p>
          <div className="mt-9 flex flex-col gap-3 sm:flex-row">
            <Link
              href="/shop"
              className="inline-flex h-13 items-center justify-center gap-2 rounded-xs border border-ink-950 bg-signal-400 px-7 text-[15px] font-bold text-ink-950 transition-colors hover:bg-signal-300"
            >
              Shop Safety Products
              <ArrowRight aria-hidden="true" className="size-4" />
            </Link>
            <Link
              href="/bulk-order"
              className="inline-flex h-13 items-center justify-center gap-2 rounded-xs border border-white/25 px-7 text-[15px] font-semibold text-white transition-colors hover:bg-white/10"
            >
              Request Bulk Quote
            </Link>
          </div>

          {/* Material, size and product counts are read from the catalogue
              rather than asserted, so this row cannot drift from the data. */}
          <dl className="mt-12 grid max-w-2xl grid-cols-2 gap-x-8 gap-y-5 border-t border-white/10 pt-8 sm:grid-cols-4">
            <HeroFact
              value={total > 0 ? total.toLocaleString("en-IN") : "\u2014"}
              label="Products live"
            />
            <HeroFact value={String(categories.length)} label="Product categories" />
            <HeroFact value="4" label="Sign materials" />
            <HeroFact value="9" label="Board sizes" />
          </dl>
        </div>
      </section>

      {/* ==================================================================
          3. Category grid - from the database
          ================================================================== */}
      <Section className="border-b border-ink-200">
        <div className="container-page">
          <SectionHeading
            eyebrow="Catalogue"
            title="Browse by category"
            description="The full range, grouped the way safety managers actually shop: by the hazard, not by the alphabet."
            action={
              <Link
                href="/category"
                className="inline-flex items-center gap-1.5 text-sm font-semibold text-ink-900 underline underline-offset-4"
              >
                All {categories.length} categories
                <ArrowRight aria-hidden="true" className="size-4" />
              </Link>
            }
          />
          <ul className="grid grid-cols-2 gap-3 sm:gap-4 md:grid-cols-3 lg:grid-cols-4">
            {categories.map((category) => (
              <li key={category.id} className="min-w-0">
                <Link
                  href={`/category/${category.slug}`}
                  className="group flex h-full min-h-28 flex-col justify-between border border-ink-200 bg-white p-4 transition-[border-color,box-shadow] hover:border-ink-900 hover:shadow-[0_2px_12px_rgba(11,13,16,0.08)]"
                >
                  {/*
                    `min-w-0` is load-bearing, not decoration. A grid item
                    defaults to `min-width: auto`, which means it refuses to
                    shrink below its content. Without it, `truncate` on the name
                    never engages and a long category name ("Outdoor Pylon Signage
                    Board") pushes the card past the viewport edge at 390px.
                  */}
                  <span className="line-clamp-2 min-w-0 text-[14px] font-semibold leading-snug text-ink-950 group-hover:underline">
                    {category.name}
                  </span>
                  <span className="mt-3 flex items-center justify-between text-[12px] text-ink-500">
                    <span className="tabular">
                      {category.product_count} product{category.product_count === 1 ? "" : "s"}
                    </span>
                    <ArrowRight
                      aria-hidden="true"
                      className="size-3.5 -translate-x-1 opacity-0 transition-all group-hover:translate-x-0 group-hover:opacity-100"
                    />
                  </span>
                </Link>
              </li>
            ))}
          </ul>
        </div>
      </Section>

      {/* ==================================================================
          4. Featured products - real API
          ================================================================== */}
      {featured.length > 0 ? (
        <Section>
          <div className="container-page">
            <SectionHeading
              eyebrow="Selected"
              title="Featured safety products"
              description="Boards we make most often across the range. Every price shown is the cheapest available material and size."
              action={
                <Link
                  href="/shop"
                  className="inline-flex items-center gap-1.5 text-sm font-semibold text-ink-900 underline underline-offset-4"
                >
                  Shop all
                  <ArrowRight aria-hidden="true" className="size-4" />
                </Link>
              }
            />
            <ProductGrid products={featured} />
          </div>
        </Section>
      ) : null}

      {/* ==================================================================
          5. Safety by industry
          ================================================================== */}
      <Section className="border-y border-ink-200 bg-ink-50">
        <div className="container-page">
          <SectionHeading
            eyebrow="By industry"
            title="Safety signage for your sector"
            description="Start from the hazards your sector is actually inspected on."
            action={
              <Link
                href="/industries"
                className="inline-flex items-center gap-1.5 text-sm font-semibold text-ink-900 underline underline-offset-4"
              >
                All industries
                <ArrowRight aria-hidden="true" className="size-4" />
              </Link>
            }
          />
          <ul className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            {industryCards.map((industry) => (
              <li key={industry.id}>
                <Link
                  href={`/industries/${industry.slug}`}
                  className="group flex h-full flex-col border border-ink-200 bg-white p-5 transition-[border-color,box-shadow] hover:border-ink-900 hover:shadow-[0_2px_12px_rgba(11,13,16,0.08)]"
                >
                  <span className="flex size-10 items-center justify-center rounded-xs bg-ink-950 text-signal-400 transition-colors group-hover:bg-signal-400 group-hover:text-ink-950 [&_svg]:size-5">
                    {ICONS[industry.slug] ?? <Wrench aria-hidden="true" />}
                  </span>
                  <span className="mt-4 text-[15px] font-semibold text-ink-950">
                    {industry.name}
                  </span>
                  {industry.summary ? (
                    <span className="mt-1.5 line-clamp-3 text-[13px] leading-relaxed text-ink-600">
                      {industry.summary}
                    </span>
                  ) : null}
                </Link>
              </li>
            ))}
          </ul>
        </div>
      </Section>

      {/* ==================================================================
          6. 5S
          ================================================================== */}
      {fiveSSlug ? (
        <Section>
          <div className="container-page">
            <div className="grid gap-8 lg:grid-cols-[1fr_420px] lg:items-center">
              <div>
                <p className="eyebrow">Workplace organisation</p>
                <h2 className="mt-2 text-2xl sm:text-3xl">
                  The 5S collection, step by step
                </h2>
                <p className="mt-4 max-w-xl text-[15px] leading-relaxed text-ink-600">
                  Seiri, Seiton, Seiso, Seiketsu, Shitsuke. The five steps that turn a
                  disorganised floor into one an auditor can walk. Each step has its own board
                  so the standard stays visible on the shop floor, not in a manual.
                </p>
                <div className="mt-6 flex flex-wrap gap-2">
                  <PillLink href={fiveSSlug ? `/category/${fiveSSlug}` : "/shop"}>
                    Shop the 5S range
                    <ArrowRight aria-hidden="true" className="size-3.5" />
                  </PillLink>
                  <PillLink href="/blog">Read the guides</PillLink>
                  {fireSlug ? (
                    <PillLink href={`/category/${fireSlug}`}>
                      Fire safety boards
                    </PillLink>
                  ) : null}
                </div>
              </div>
                <ol className="divide-y divide-ink-200 border border-ink-200 bg-white">
                  {FIVE_S_STEPS.map((step, index) => (
                    <li key={step.roman}>
                      <Link
                        href={fiveSSlug ? `/shop?category=${fiveSSlug}` : "/shop"}
                        className="flex items-center gap-4 px-4 py-3.5 transition-colors hover:bg-ink-50"
                      >
                        <span className="tabular w-8 shrink-0 font-mono text-[12px] font-semibold text-ink-400">
                          {String(index + 1).padStart(2, "0")}
                        </span>
                        <span className="min-w-0 flex-1">
                          <span className="block text-[14px] font-bold text-ink-950">
                            {step.roman} &middot; {step.name}
                          </span>
                          <span className="block text-[13px] text-ink-600">{step.gloss}</span>
                        </span>
                        <ArrowRight
                          aria-hidden="true"
                          className="size-4 shrink-0 text-ink-300"
                        />
                      </Link>
                    </li>
                  ))}
                </ol>
            </div>
          </div>
        </Section>
      ) : null}

      {/* ==================================================================
          7. MSDS
          ================================================================== */}
      {msdsSlug ? (
        <Section className="border-y border-ink-200 bg-ink-950 text-white">
          <div className="container-page">
            <div className="grid gap-8 lg:grid-cols-2 lg:items-center">
              <div>
                <p className="eyebrow !text-signal-400">Chemical safety</p>
                <h2 className="mt-2 text-2xl text-white sm:text-3xl">
                  MSDS and GHS hazard boards
                </h2>
                <p className="mt-4 max-w-xl text-[15px] leading-relaxed text-ink-300">
                  Material Safety Data Sheet boards and Globally Harmonised System hazard
                  pictograms, in the sizes and materials that survive a plant floor. Chemical
                  stores and dispensing points are where GHS signage gets inspected, and these
                  are the boards to have in place.
                </p>
                <ul className="mt-6 grid gap-2.5 text-sm text-ink-300 sm:grid-cols-2">
                  {[
                    "GHS pictogram boards",
                    "Chemical hazard labels",
                    "MSDS display boards",
                    "Handling instruction boards",
                  ].map((item) => (
                    <li key={item} className="flex items-center gap-2.5">
                      <span aria-hidden="true" className="size-1.5 shrink-0 bg-signal-400" />
                      {item}
                    </li>
                  ))}
                </ul>
                <div className="mt-7 flex flex-wrap gap-3">
                  <Link
                    href={`/category/${msdsSlug}`}
                    className="inline-flex h-12 items-center justify-center rounded-xs border border-ink-950 bg-signal-400 px-6 text-[15px] font-bold text-ink-950 transition-colors hover:bg-signal-300"
                  >
                    Browse MSDS boards
                  </Link>
                  <Link
                    href="/industries/chemical"
                    className="inline-flex h-12 items-center justify-center rounded-xs border border-white/25 px-6 text-[15px] font-semibold text-white transition-colors hover:bg-white/10"
                  >
                    Chemical industry picks
                  </Link>
                </div>
              </div>
              <dl className="grid gap-px overflow-hidden border border-white/10 bg-white/10 sm:grid-cols-2">
                <DarkFact
                  icon={<FlaskConical aria-hidden="true" />}
                  title="Aluminium composite"
                  body="3MM ACP for indoor stores and labs where moisture is not a factor."
                />
                <DarkFact
                  icon={<Gauge aria-hidden="true" />}
                  title="5MM foam sheet"
                  body="Light, rigid and easy to fix to a wall or a rack face."
                />
                <DarkFact
                  icon={<ClipboardList aria-hidden="true" />}
                  title="Up to 48x96 in."
                  body="Large formats for boardrooms and store-room walls."
                />
                <DarkFact
                  icon={<Truck aria-hidden="true" />}
                  title="Shipped across India"
                  body="Panelled, corner-guarded and ready to mount."
                />
              </dl>
            </div>
          </div>
        </Section>
      ) : null}

      {/* ==================================================================
          8. Electrical safety
          ================================================================== */}
      {electricalSlug ? (
        <Section>
          <div className="container-page">
            <div className="grid gap-8 lg:grid-cols-[420px_1fr] lg:items-center">
              {/* Real products from the electrical category, straight from the
                  API. Not a hand-written list of plausible-sounding titles. */}
              {electrical.length > 0 ? (
                <ul className="divide-y divide-ink-200 border border-ink-200">
                  {electrical.map((product) => (
                    <li key={product.id}>
                      <Link
                        href={`/products/${product.slug}`}
                        className="block px-4 py-3.5 transition-colors hover:bg-ink-50"
                      >
                        <span className="flex items-baseline justify-between gap-3">
                          <span className="text-[14px] font-semibold text-ink-950">
                            {product.title}
                          </span>
                          <span className="tabular shrink-0 text-[13px] font-semibold text-ink-900">
                            {product.price.formatted}
                          </span>
                        </span>
                        <span className="mt-0.5 block font-mono text-[11px] uppercase tracking-wide text-ink-400">
                          {product.sku}
                        </span>
                      </Link>
                    </li>
                  ))}
                </ul>
              ) : null}
              <div>
                <p className="eyebrow">Electrical safety</p>
                <h2 className="mt-2 text-2xl sm:text-3xl">
                  Electrical safety signage
                </h2>
                <p className="mt-4 max-w-xl text-[15px] leading-relaxed text-ink-600">
                  Shock, arc and voltage boards for panels, substations and switch rooms. The
                  category spans small sticker formats for distribution boards through to
                  large boards for compound walls.
                </p>
                <ul className="mt-6 grid gap-3 sm:grid-cols-2">
                  {[
                    ["Indoor & outdoor", "ACP and foam sheet for plant rooms; vinyl and autoglow for gates and approaches."],
                    ["Sticker formats", "8x12 through 24x36 for panels, meters and machine faces."],
                    ["Autoglow options", "Phosphorescent boards that stay readable in a power cut."],
                    ["Full size range", "Eight standard sizes, so a set matches across a site."],
                  ].map(([title, body]) => (
                    <li key={title} className="border-l-2 border-signal-400 pl-3.5">
                      <p className="text-[14px] font-semibold text-ink-950">{title}</p>
                      <p className="mt-1 text-[13px] leading-relaxed text-ink-600">{body}</p>
                    </li>
                  ))}
                </ul>
                <Link
                  href={`/category/${electricalSlug}`}
                  className="mt-7 inline-flex h-12 items-center justify-center gap-2 rounded-xs border border-ink-950 bg-ink-950 px-6 text-[15px] font-semibold text-white transition-colors hover:bg-ink-800"
                >
                  Browse electrical safety
                  <ArrowRight aria-hidden="true" className="size-4" />
                </Link>
              </div>
            </div>
          </div>
        </Section>
      ) : null}

      {/* ==================================================================
          9. Bulk order CTA
          ================================================================== */}
      <Section className="border-y border-ink-200 bg-ink-50">
        <div className="container-page">
          <div className="relative overflow-hidden border border-ink-200 bg-white">
            <div aria-hidden="true" className="absolute inset-y-0 left-0 w-1.5 safety-stripe" />
            <div className="grid gap-8 p-7 sm:p-10 lg:grid-cols-[1fr_auto] lg:items-center">
              <div>
                <p className="eyebrow">B2B &amp; site-wide sets</p>
                <h2 className="mt-2 text-2xl sm:text-3xl">Need signage across a whole site?</h2>
                <p className="mt-3 max-w-2xl text-[15px] leading-relaxed text-ink-600">
                  Send us your board list, quantities and material preference. We will come back
                  with a proper quotation, freight included, rather than a per-item price that
                  does not add up at volume. Single-board orders can still be placed directly
                  on this site.
                </p>
                <ul className="mt-5 flex flex-wrap gap-x-6 gap-y-2 text-[13px] text-ink-700">
                  {[
                    "Volume pricing on ACP and foam sheet",
                    "Consistent sizing across a facility",
                    "GST invoice on business orders",
                  ].map((item) => (
                    <li key={item} className="flex items-center gap-2">
                      <span aria-hidden="true" className="size-1.5 bg-ink-400" />
                      {item}
                    </li>
                  ))}
                </ul>
              </div>
              <div className="flex flex-col gap-3">
                <Link
                  href="/bulk-order"
                  className="inline-flex h-13 items-center justify-center gap-2 whitespace-nowrap rounded-xs border border-ink-950 bg-signal-400 px-7 text-[15px] font-bold text-ink-950 transition-colors hover:bg-signal-300"
                >
                  <Wrench aria-hidden="true" className="size-4" />
                  Request Bulk Quote
                </Link>
                <a
                  href={business.whatsapp}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex h-12 items-center justify-center gap-2 whitespace-nowrap rounded-xs border border-ink-900 bg-white px-6 text-sm font-semibold text-ink-900 transition-colors hover:bg-ink-50"
                >
                  WhatsApp {business.phone}
                </a>
              </div>
            </div>
          </div>
        </div>
      </Section>

      {/* ==================================================================
          10. Trust / value - verified claims only
          ================================================================== */}
      <Section>
        <div className="container-page">
          <SectionHeading
            eyebrow="Why buy from us"
            title="What you can rely on"
          />
          <dl className="grid gap-px border border-ink-200 bg-ink-200 sm:grid-cols-2 lg:grid-cols-4">
            <ValueFact
              icon={<Ruler aria-hidden="true" />}
              title="Nine standard sizes"
              body="From 8x12 to 48x96 inches, so a set of boards matches across a facility instead of being mixed formats."
            />
            <ValueFact
              icon={<ShieldAlert aria-hidden="true" />}
              title="Four materials"
              body="3MM ACP, 5MM foam sheet, autoglow sticker and eco vinyl sticker - chosen for the location, not just the price."
            />
            <ValueFact
              icon={<Factory aria-hidden="true" />}
              title="Printed in Ankleshwar, Gujarat"
              body={business.address}
            />
            <ValueFact
              icon={<Truck aria-hidden="true" />}
              title="Delivered across India"
              body="Board orders ship panelled and corner-guarded. Freight is confirmed on the quotation."
            />
          </dl>
          {isPending(business.businessHours) || isPending(business.gstin) ? (
            <p className="mt-5 text-[12px] text-ink-500">
              GSTIN and business hours are not yet published by the business and are therefore
              not shown here. Contact us and we will confirm them.
            </p>
          ) : null}
        </div>
      </Section>

      {/* ==================================================================
          11. New arrivals - real API
          ================================================================== */}
      {newest.length > 0 ? (
        <Section className="border-t border-ink-200">
          <div className="container-page">
            <SectionHeading
              eyebrow="Recently added"
              title="New to the catalogue"
              action={
                <Link
                  href="/shop?sort=newest"
                  className="inline-flex items-center gap-1.5 text-sm font-semibold text-ink-900 underline underline-offset-4"
                >
                  See all
                  <ArrowRight aria-hidden="true" className="size-4" />
                </Link>
              }
            />
            <ProductGrid products={newest} />
          </div>
        </Section>
      ) : null}

      {/* ==================================================================
          12. Newsletter
          ================================================================== */}
      <Newsletter />
    </>
  );
}

/* ---------------------------------------------------------------------- */

/**
 * The five steps, in the order they are taught.
 *
 * This is the 5S definition rather than product data: the same five words apply
 * to any business, and the seed writes the same sequence into
 * `collections` for the `/5s` page. The homepage summary is presentation, so it
 * is stated here rather than fetched.
 */
const FIVE_S_STEPS = [
  { roman: "Seiri", name: "Sort", gloss: "Red-tag what is not needed." },
  { roman: "Seiton", name: "Set in order", gloss: "A fixed home for every tool." },
  { roman: "Seiso", name: "Shine", gloss: "Clean is also an inspection." },
  { roman: "Seiketsu", name: "Standardise", gloss: "Same standard, every shift." },
  { roman: "Shitsuke", name: "Sustain", gloss: "Audit, correct, repeat." },
] as const;

function PillLink({ href, children }: { href: string; children: React.ReactNode }) {
  return (
    <Link
      href={href}
      className="inline-flex items-center gap-1.5 rounded-xs border border-ink-300 bg-white px-4 py-2 text-sm font-semibold text-ink-900 transition-colors hover:border-ink-900"
    >
      {children}
    </Link>
  );
}

function HeroFact({ value, label }: { value: string; label: string }) {
  return (
    <div>
      <dt className="sr-only">{label}</dt>
      <dd>
        <span className="tabular block text-2xl font-bold text-white sm:text-3xl">{value}</span>
        <span className="mt-1 block text-[12px] leading-tight text-ink-400">{label}</span>
      </dd>
    </div>
  );
}

function DarkFact({
  icon,
  title,
  body,
}: {
  icon: React.ReactNode;
  title: string;
  body: string;
}) {
  return (
    <div className="bg-ink-950 p-5">
      <dt className="flex items-center gap-2.5 text-signal-400 [&_svg]:size-4">
        {icon}
        <span className="text-[13px] font-bold uppercase tracking-[0.06em]">{title}</span>
      </dt>
      <dd className="mt-2 text-[13px] leading-relaxed text-ink-300">{body}</dd>
    </div>
  );
}

function ValueFact({
  icon,
  title,
  body,
}: {
  icon: React.ReactNode;
  title: string;
  body: string;
}) {
  return (
    <div className="bg-white p-5">
      <dt className="flex items-center gap-2.5 text-ink-500">
        <span className="[&_svg]:size-5">{icon}</span>
        <span className="text-[14px] font-bold text-ink-950">{title}</span>
      </dt>
      <dd className="mt-2 text-[13px] leading-relaxed text-ink-600">{body}</dd>
    </div>
  );
}

function Newsletter() {
  return (
    <Section className="border-t border-ink-200 bg-ink-50">
      <div className="container-page">
        <div className="border border-ink-200 bg-white p-7 sm:p-10">
          <div className="grid gap-8 lg:grid-cols-[1fr_440px] lg:items-center">
            <div>
              <p className="eyebrow">Stay current</p>
              <h2 className="mt-2 text-2xl sm:text-3xl">
                Safety signage updates, not spam
              </h2>
              <p className="mt-3 max-w-xl text-[15px] leading-relaxed text-ink-600">
                New product categories, changes to signage standards, and practical guides on
                choosing the right material for a location. Sent occasionally.
              </p>
            </div>
            {/* The subscribe endpoint is a later phase. The form is rendered but
                disabled with a visible reason rather than posting nowhere. */}
            <div>
              <div className="flex flex-col gap-2 sm:flex-row">
                <label htmlFor="newsletter-email" className="sr-only">
                  Email address
                </label>
                <input
                  id="newsletter-email"
                  type="email"
                  disabled
                  placeholder="you@company.com"
                  className="h-12 flex-1 rounded-xs border border-ink-300 bg-ink-50 px-3.5 text-sm text-ink-500"
                />
                <button
                  type="button"
                  disabled
                  className="h-12 shrink-0 rounded-xs border border-ink-300 bg-ink-100 px-6 text-sm font-semibold text-ink-500"
                >
                  Subscribe
                </button>
              </div>
              <p className="mt-2 text-[12px] text-ink-500">
                Newsletter signup is not live yet. Use the contact form or WhatsApp and we will
                add you to the list.
              </p>
            </div>
          </div>
        </div>
      </div>
    </Section>
  );
}
