# Storefront — Phase 1

The customer-facing Next.js application for Safety Poster Prints. Replaces the
`create-next-app` scaffold entirely.

## Running it

```bash
# 1. Backend on :8000 (see ../backend)
# 2. This app on :3000
npm install
cp .env.example .env.local
npm run dev
```

## What it does and does not do

**Working:** the full catalogue browsing experience. Every route below renders
real data from the seeded PostgreSQL database through the FastAPI backend.

**Not working, and says so on screen:** cart persistence beyond the browser
device, checkout, payment, and account sign-in. Each of those is a later phase.
Where a page would otherwise be a dead end - checkout, the contact form, the
quote form, the newsletter box - it states plainly that it is not connected and
routes the customer to WhatsApp, phone or email, which are verified and working.
A form that silently discards input is worse than no form.

## Routes

| Route | Rendering | Notes |
|---|---|---|
| `/` | ISR 30s | Hero, category grid, featured, industries, 5S, MSDS, electrical, bulk CTA, trust, new arrivals |
| `/shop` | dynamic | Full filtering, sorting, pagination |
| `/category` | dynamic | All 18 categories with real counts and a product preview each |
| `/category/[slug]` | dynamic | SEO slugs preserved exactly as stored |
| `/products/[slug]` | dynamic | Material x Size selector, gallery, specs, structured data |
| `/search` | dynamic | Server-rendered results, `noindex` |
| `/cart` | static | Variant-level lines, local persistence |
| `/checkout` | static | States that payment is not connected |
| `/account/*` | static | Shell + explicit signed-out state |
| `/bulk-order` | dynamic | Multi-line board list, local validation |
| `/industries`, `/industries/[slug]` | dynamic | 10 industries, Markdown bodies, curated picks |
| `/blog`, `/blog/[slug]` | dynamic | Guides with FAQ schema |
| `/5s`, `/msds` | dynamic | Editorial collection pages |
| `/about`, `/contact` | static | Verified facts only |
| `/policies/[slug]` | SSG | Structure with explicit gaps where text is unpublished |
| `/sitemap.xml`, `/robots.txt` | — | Generated from the database |

## Architecture

```
src/
  app/                  routes; no data fetching outside lib/api
  components/
    catalog/            ProductCard, ProductGrid, gallery, display primitives
    product/            VariantSelector - the Material x Size matrix
    filters/            URL-driven filter controls
    cart/               CartProvider (localStorage), CartView
    wishlist/           WishlistProvider (localStorage)
    layout/             AnnouncementBar, SiteHeader, SiteFooter, Wordmark
    content/            Markdown renderer
    ui/                 Button, Badge, Skeleton, EmptyState, ErrorState, form controls
  lib/
    api/                client.ts, catalog.ts, content.ts, types.ts
    variants.ts         the variant matrix - pure, heavily unit tested
    filters.ts          URL filter state
    localStore.ts       useSyncExternalStore over localStorage
    money.ts            rupee formatting
    images.ts           image URL resolution
    env.ts              config and verified business facts
```

### Three decisions worth knowing

**Prices are never computed in the browser.** Every amount shown came from the
server. The cart's `totals()` is explicitly typed `isEstimate: true` and the UI
says shipping and GST are calculated at checkout. A storefront that can
miscompute its own total is a storefront that will eventually lose money.

**Materials and sizes come from the database, always.** `lib/variants.ts` derives
the option lists from `product.options` and never assumes a material or a size
exists. A product sold in only two sizes renders two size buttons.

**`lib/env.ts` reads `process.env` as literals.** Next.js inlines
`NEXT_PUBLIC_*` into the client bundle only for statically analysable member
access. A dynamic `process.env[name]` lookup survives into the browser and
evaluates to `undefined`, throwing at module load. This bug is invisible to
`next build` and only appears in a real browser - which is why the Playwright
sweep exists. See the comment at the top of that file.

## Testing

```bash
npm run typecheck   # tsc --noEmit
npm run lint        # eslint, 0 errors 0 warnings
npm test            # 173 unit/component tests (vitest)
npm run qa          # 39 browser tests (playwright) - needs the app on :3100
```

`npm run qa` requires the built app running:

```bash
npm run build && npm run start -- -p 3100
npx playwright install chromium   # first run only
npm run qa
```

### What the browser sweep covers

Five viewports (390, 430, 768, 1024, 1440) across home, shop, category, product
and cart, checking the two things a build cannot: real horizontal overflow, and
console errors. Plus the mobile drawer, the mobile filter sheet, the Material x
Size selector end to end, the cart round trip, `h1` and skip-link presence,
focus order, JSON-LD, the sitemap and robots.txt.

It has already caught four real bugs that no unit test or build would have:
the `env.ts` bundling bug above, a 31px overflow from a missing `min-w-0` on
flex children, a filter checkbox that did not tick until the server responded,
and a header that pushed the cart icon 220px off-screen at 1024px.

### Overflow detection, precisely

The naive check - "does any element's right edge exceed the viewport?" - is
wrong and reports a false failure on every page, because the category rail is
deliberately scrollable. The sweep instead asserts two things that actually mean
"the page is broken": the document can be panned sideways, or an element
overflows with no ancestor clipping it. An `overflow: hidden` ancestor counts as
a valid excuse only when it is deliberately truncating (`text-overflow: ellipsis`
or a line clamp) - a plain `hidden` that silently cuts text off is a failure.

## Known limitations

- **Cart, wishlist and the "buy now" quantity live in `localStorage`.** The cart
  API is phase 2. Line identity is already the variant id, prices are already
  server-sourced, and `CartProvider` is already isolated behind a context, so
  swapping in the real API touches one file.
- **Account sign-in is not built.** The auth backend is verified; there is no
  screen. Every account route states this and offers guest checkout.
- **404 responses return HTTP 200.** `notFound()` is called from
  `generateMetadata` so the status is correct wherever the shell has not already
  flushed, but the async root layout resolves before the body renders, so a
  missing product or category is a soft 404. The response always carries
  `<meta name="robots" content="noindex">`, which is what stops a soft 404 from
  being indexed. A Route Handler or a non-streaming shell would be needed to fix
  the status itself.
- **The hero's right half is empty on desktop.** Filling it needs a real product
  photograph; the seeded artwork is a labelled placeholder and inventing a hero
  image was not an option.
- **Every seeded product has a complete material x size matrix**, so the
  "combination unavailable, disabled" state cannot be seen in the browser against
  current data. It is fully covered by unit tests against an irregular fixture,
  and the browser test checks the API's matrix and fails loudly if the import
  pipeline later produces a sparse one.
- **Reviews, coupons and contact messages have no API.** The UI shows an explicit
  empty state rather than placeholder content.
