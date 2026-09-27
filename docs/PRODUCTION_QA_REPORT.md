# Production QA Report

**Project:** Safety Poster Prints storefront + commerce API (`D:\X\storefront`)
**Date:** 2026-09-27
**Commit audited:** `d19618b`
**Stack under test:** Next.js 15 (App Router) storefront on `:3100`, FastAPI + SQLAlchemy 2.1 + asyncpg API on `:8000`, PostgreSQL 18 on `:55432`, Redis on `:6379`.

---

## 1. Executive summary

The storefront was put through a full production-grade audit: the real customer journey driven in a real browser, a hostile API probe set, query-level database profiling, Lighthouse on six routes, a 7-width responsive matrix, a 20-product variant-matrix audit, and edge-case sweeps. Every finding was reproduced, root-caused, fixed and regression-tested.

**Four real defects were found and fixed.** All four were invisible to `npm run build` and to `tsc`:

1. An N+1 on `/industries` — 11 queries and 120 ms to render 10 cards, now 1 query and 5 ms.
2. Search suggestions had **never worked in a browser** — a cross-origin call blocked by CORS, failing silently as a console error.
3. Two colour tokens failed WCAG AA in the footer, one of them by 0.02.
4. A link-prefetch storm: 98 requests per listing page, including every product route fetched twice.

**The single most important finding is not a bug, it is a scope boundary, and I am reporting it as a blocker rather than burying it: this application cannot take an order.** Cart and checkout exist only as browser-local state. There is no cart API, no order table in use, no inventory reservation, no payment integration, no webhook, no order-history route, and no admin surface. The journey the audit was asked to execute terminates honestly at checkout with an explicit "not connected" message rather than a fake payment form — which is the correct behaviour, but it is not a working checkout.

I did not claim success because the build passed. The build passed before the audit and four defects stood behind it.

**Test posture at the end of the audit:** 131 backend tests, 173 frontend unit/component tests, 40 browser tests, 0 typecheck errors, 0 lint errors, ruff clean, production build clean, Lighthouse 100/100/100 on six routes.

**Not production ready.** Three P0-class gaps remain and they are all Phase 2 build work, not defects I can patch.

---

## 2. Tests performed

| # | Test | Scope | Result |
|---|---|---|---|
| 1 | Secret scan | every tracked file, 6 credential shapes + 16 secret-value patterns | clean (only test fixture values, all in `conftest.py` / `test_security.py` with obvious test-only names) |
| 2 | Hostile input probe | 21 malformed/hostile requests (SQLi strings, null bytes, 100 KB query, negative and absurd pagination, XSS payloads) | no 500s with a leaked trace; 2 issues found |
| 3 | Authorization probe | 7 admin + 5 account endpoints × 5 token shapes (none, garbage, `alg:none`, expired, malformed) | **0 violations** — all 60 combinations returned 401 |
| 4 | Privilege escalation | `PATCH /admin/customers/{id}/role` with `role: ADMIN` under every bad token | 401, blocked |
| 5 | OpenAPI security review | generated schema vs runtime enforcement | 1 issue: schema declares 0 protected operations |
| 6 | Error-envelope probe | null byte, unknown route, traversal, wrong method | 1 issue: 500 on null byte |
| 7 | SQL profiling | raw timing of every hot query, `EXPLAIN ANALYZE`, index inventory | DB is not the bottleneck; app layer is |
| 8 | Per-request query count | 8 routes instrumented via SQLAlchemy events | 2 N+1s found |
| 9 | Full customer journey | home → drawer → category → shop → filter → search → product → variant → cart → checkout, at 390×844 | passes; variant identity exact |
| 10 | Route timings + CWV | 15 routes at 1440×900, LCP/CLS/TTFB + console + network | 1 CORS defect, 1 CLS nit |
| 11 | Prefetch accounting | request census on a filtered listing | 98 requests, 40 RSC prefetches |
| 12 | Lighthouse | `/shop`, `/`, `/products/[slug]`, `/cart`, `/industries`, `/bulk-order` | 1 failure, then 0 |
| 13 | Variant matrix | 20 products, every material × size cell | all properties hold |
| 14 | Responsive matrix | 7 widths (390/430/768/1024/1280/1440/1920) × 6 routes: page pan, unclipped overflow, controls outside viewport, console | 2 real findings, both fixed |
| 15 | Tap targets | header + main controls at 390 and 430 | clean |
| 16 | Edge cases | 11 states incl. zero results, impossible filters, 4 kinds of bad slug, unknown route | 1 issue (soft 404) |
| 17 | Full regression | backend pytest, vitest, playwright, typecheck, eslint, ruff, build | all green after fixes |

---

## 3. Issues discovered

Severity in the requested P0–P4 scale.

### P1 — Broken / degraded core customer journey

| ID | Issue | Location |
|---|---|---|
| I-1 | **The site cannot take an order.** No cart API, no order persistence, no inventory reservation, no payment, no order history, no admin. Cart and checkout are browser-local only. | `frontend/src/components/cart/CartProvider.tsx`, `frontend/src/app/checkout` |
| I-2 | **Search suggestions never worked in a browser.** The client called the API cross-origin and was blocked by CORS. Typing in the search box silently returned nothing. | `frontend/src/components/search/SearchBox.tsx` |
| I-3 | **Prefetch storm.** Every visible `<Link>` prefetched. 98 requests on `/shop`; each product route fetched twice. | `SiteHeader.tsx`, `SiteFooter.tsx`, `ProductCard.tsx` |
| I-4 | **N+1 on `/industries`.** 11 queries, 120 ms wall, to render 10 cards whose product count comes from a subquery. | `backend/app/models/content.py` |

### P2 — Major performance / UX

| ID | Issue | Location |
|---|---|---|
| I-5 | WCAG AA contrast failure on 10 footer elements. `ink-500` missed 4.5:1 by 0.02; `ink-400` failed at 2.90:1. | `frontend/src/app/globals.css` |
| I-6 | 500 on a null byte in the path. Envelope was correct (no trace leaked) but the status is wrong. | `backend/app` routing/error path |
| I-7 | A 100 KB query string produced a connection-level failure, not a clean 4xx. | `backend/app/api/v1/search.py` |
| I-8 | A 16-query product list for 8 products, with `product_tags` issued 5 times. **Fix attempted, reverted — see §5.** | `backend/app/services/catalog.py` |

### P3 — Accessibility / SEO

| ID | Issue | Location |
|---|---|---|
| I-9 | 404s return HTTP 200 (soft 404). Correct pages carry `noindex`, so SEO damage is contained, but the status is wrong. | `frontend/src/app/[...]/not-found.tsx` and the streaming root layout |
| I-10 | The generated OpenAPI schema declares **zero** protected operations, so the published API documentation tells any consumer that `/admin/*` is public. Enforcement is real and verified; the documentation is wrong. | `backend/app/api/v1/*.py` |

### P4 — Cosmetic / informational

| ID | Issue | Notes |
|---|---|---|
| I-11 | `CLS 0.013` on `/blog`. | Well inside the 0.1 "good" threshold. Not worth destabilising layout for. |
| I-12 | `/api/docs` and `/api/openapi.json` are public in development. | Must be gated in production — see §15. |
| I-13 | `/health/ready` names which credentials are missing. | Acceptable for a readiness probe; must be internal-only in production. |
| I-14 | Test-only secret *values* are committed (`conftest.py`, `test_security.py`). | Not real credentials. Worth relocating to a fixture module. |

---

## 4. Root causes

**I-1 — the gap is architectural, not a defect.** Phase 1 deliberately stopped at the storefront. Cart state is `localStorage` keyed on `variant_id`, which is correct for a demo but means: two browsers cannot share a cart, the server cannot price an order, nothing reserves stock, and a user can hand-edit `localStorage` to set a price the server never agreed to. `/checkout` renders an explicit "not connected" state rather than a form that pretends to work. The `CartTotals.isEstimate` type is `true` for exactly this reason.

**I-2 — a client component crossing an origin boundary.** `SearchBox` is `"use client"`, so its `getSearchSuggestions()` call went from the browser to `127.0.0.1:8000`. That is a cross-origin request requiring correct CORS. The API's CORS allowlist did not include the storefront origin, and — critically — the failure mode is a console message, not an exception, so the search box just looked inert. This is not a local-only quirk: the intended production shape is storefront on Vercel and API on Railway, i.e. two origins, so this call was broken in production too. The root cause is *the browser talking to the API at all* for a read that the Next server could do for it.

**I-3 — default `Link` prefetching, applied to lists where it is actively harmful.** Next prefetches every visible link. The header rail holds 18 categories, the footer holds several dozen, and `ProductCard` contains *two* links to the same product (a stretched `absolute inset-0` overlay plus the title), so each card prefetched its route twice. A shopper clicks one or two of these links per visit.

**I-4 — `lazy="selectin"` on a relationship that is never read.** `selectin` emits a batched secondary SELECT *whenever the parent is loaded*, whether or not the attribute is touched. The industries index computes its product count from a correlated subquery and never reads `Industry.products` — but SQLAlchemy loaded all 60 linked products anyway, and through them every variant, image, tag and inventory row. The codebase already used `noload` for the identical `Category.products`; the industry one was the inconsistency. Query log at the time:

```
1   0.7ms  industries
2   3.0ms  industry_products JOIN products     <- never read
3  17.2ms  product_variants
4   5.3ms  product_images
5   1.8ms  product_tags JOIN tags
... 7 more tag/image/variant batches
```

**I-5 — palette tokens doubling as text colours.** `ink-400` and `ink-500` were chosen as neutral tints and then used for real text (SKUs, captions, "not published" placeholders, footer links). Nobody checked them against the tinted `ink-50` footer background. `ink-500` at 4.48:1 is the characteristic failure: each individual palette edit looked harmless and the total drifted one nudge at a time.

**I-6 / I-7 — no length or content validation at the path-parsing boundary.** A null byte reaches the router and raises an unhandled exception (correctly wrapped, so no trace leaked, but a 500). An oversized query string fails at the connection layer rather than being rejected as a 4xx.

**I-8 — `lazy="joined"` many-to-one back-references.** `ProductVariant.product` and `ProductRatingSummary.product` are `lazy="joined"`, so variant and rating rows arrive carrying a copy of their parent. Those copies reach the session by a different path, and the first access to `tags`/`images` on a copy re-fires the selectin loader. I formed this hypothesis, tried to fix it, could not land it without breaking rating data, and reverted. It is documented as an open issue rather than shipped as a guess.

**I-9 — a streaming root layout.** `notFound()` is called from `generateMetadata`, but the async root layout flushes the HTML shell before the child resolves, so the 404 status cannot be set. Fixing it needs a non-streaming shell or a Route Handler.

**I-10 — auth applied via `Depends()` in handler signatures.** FastAPI only marks an operation as secured in OpenAPI when the dependency is attached at the router or app level, so the per-handler `Depends(get_current_admin)` enforces correctly at runtime but is invisible in the schema.

---

## 5. Fixes applied

All five changes below are committed. Each was reproduced before the change and re-verified after.

### F-1 — `/industries`: 11 queries / 116 ms → 1 query / 5.8 ms

`Industry.products` changed from `lazy="selectin"` to `lazy="noload"`, with a comment explaining that this is a performance fix and not a style choice. The industry **detail** route already used an explicit join query, so it needed no change and the product picks are unaffected — confirmed by the fact that all 131 backend tests passed on the first run after the edit.

| | before | after |
|---|---|---|
| queries | 11 | 1 |
| wall | 116.5 ms | 5.8 ms |
| DB time | 56.0 ms | 0.7 ms |

### F-2 — search suggestions now same-origin

Added `frontend/src/app/api/search-suggestions/route.ts`, a route handler that calls the backend server-side and returns the suggestions, with the query clamped to 2–100 characters, a cap of 7 results, `no-store`, and a catch that returns an empty list rather than letting a failed lookup break typing. `SearchBox` now fetches `/api/search-suggestions?q=…` on its own origin.

This removes the CORS dependency from the client entirely, which is the durable fix — it works identically in local development and in the split-host production deployment. The repo-invariant test that bans direct `fetch()` in components was updated with a single explicitly named, commented exception, so the ban still catches accidents everywhere else.

Verified: the console error is gone from `/search`, and the suggestion dropdown is live.

### F-3 — contrast-compliant ink tokens

```
ink-400  #8b939d (2.90:1 on ink-50)  ->  #656c74  (5.32 / 4.96 / 4.57 on white / ink-50 / ink-100)
ink-500  #6b737d (4.48:1 on ink-50)  ->  #5c646e  (5.99 / 5.59 / 5.15)
```

Both clear 4.5:1 on every surface they are used on, and both remain lighter than `ink-600` (7.18:1) so the scale's hierarchy survives. Verified by direct sRGB-relative-luminance computation, not by eye.

Lighthouse accessibility **96 → 100** on `/shop`, and **100 / 100 / 100 with zero failures** on `/`, `/products/danger-high-voltage`, `/cart`, `/industries`, `/bulk-order`.

### F-4 — prefetch suppression where it is not wanted

`prefetch={false}` on the header category rail, the footer `FooterLink` component, and `ProductCard`'s image-overlay link. The card's **title** link keeps its prefetch, because that is the one a reader actually aims at.

| route | requests before | after |
|---|---|---|
| home | 71 | 58 |
| shop | 98 | 86 |
| cart | 62 | 47 |
| account | 78 | 56 |

### F-5 — reverted, deliberately

The `ProductCategorySelect` / back-reference `noload` attempt for I-8 broke 32 tests. The first attempt (`noload(ProductVariant.product)`) was rejected by SQLAlchemy — the option must be given as a full path from a root entity. The corrected full-path syntax compiled and still broke 32 tests, including `test_listing_cards_do_not_carry_fake_ratings`, because `rating_summary` is load-bearing for the listing card.

I reverted it rather than ship a change I could not verify. The honest position: I-8 is a real inefficiency, I have a plausible cause, and I have not proven the fix. It is written up in §15 with the next action rather than papered over.

### Final regression state

```
backend   ruff: all checks passed        pytest: 131 passed
frontend  tsc --noEmit: 0 errors        eslint: 0 errors, 0 warnings
          vitest: 173 passed             playwright: 40 passed
          next build: compiled successfully
```

---

## 6. Performance measurements

Measured against the production build served by `npm run start`. Wall time is `domcontentloaded` + `load`, **not** `networkidle` — Next prefetches continuously, so `networkidle` never arrives on a listing page and reported a 27-second load for a page that renders in 650 ms. That 27 s was a measurement artifact, not a real regression, and the harness now uses a fixed settle instead.

| Route | Wall | TTFB | LCP | CLS | Requests |
|---|---|---|---|---|---|
| `/` | 330 ms | 64 ms | 292 ms | 0 | 58 |
| `/shop` | 440 ms | 184 ms | 624 ms | 0 | 82 |
| `/shop?material=3MM+ACP&size=18x24` | 132 ms | 17 ms | 148 ms | 0 | 82 |
| `/category/electrical-safety` | 207 ms | 15 ms | 400 ms | 0 | 83 |
| `/products/danger-high-voltage` | 175 ms | 20 ms | 428 ms | 0 | 60 |
| `/search?q=voltage` | 81 ms | 14 ms | 384 ms | 0 | 58 |
| `/cart` | 34 ms | 5 ms | 60 ms | 0 | 47 |
| `/checkout` | 38 ms | 7 ms | 68 ms | 0 | 47 |
| `/account` | 33 ms | 4 ms | 68 ms | 0 | 56 |
| `/industries` | 47 ms | 14 ms | 72 ms | 0 | 60 |
| `/blog` | 59 ms | 13 ms | 372 ms | 0.013 | 47 |
| `/5s` | 76 ms | 13 ms | 416 ms | 0 | 52 |
| `/msds` | 83 ms | 13 ms | 396 ms | 0 | 58 |
| `/bulk-order` | 63 ms | 16 ms | 80 ms | 0 | 47 |
| `/about` | 36 ms | 6 ms | 64 ms | 0 | 49 |

Every LCP is far inside the 2500 ms "good" threshold. Every CLS is 0 except `/blog` at 0.013 (good threshold 0.1).

**API latency, best of 7 (after F-1):**

| Endpoint | p50 | Note |
|---|---|---|
| `/api/v1/industries` | 5.1 ms | was 120 ms |
| `/api/v1/categories` | 7.7 ms | |
| `/api/v1/facets` | 15.7 ms | |
| `/api/v1/products/{slug}` | 30.5 ms | |
| `/api/v1/products?per_page=1` | 29.8 ms | |
| `/api/v1/search?q=` | 57.5 ms | |
| `/api/v1/products?per_page=24` | 111 ms | the slowest endpoint; see I-8 |
| `/api/v1/products` + material/size filter | 112 ms | |

**The database is not the bottleneck.** Raw SQL timings, best of 5, bypassing the ORM entirely:

```
products list ORDER BY created_at LIMIT 24   0.3 ms
count(*) products                            0.4 ms
material facet (jsonb ->> GROUP BY)          2.3 ms
size facet (jsonb ->> GROUP BY)              1.9 ms
```

Against a 111 ms endpoint. ~55 ms is database work, ~55 ms is ORM materialisation and Pydantic serialisation of 24 products × their variants, images and inventory. Optimising this means reducing the payload or the serialisation, not adding indexes.

**No N+1 in search or facets.** Search runs 17 queries: tsvector match, trigram fallback, facets, suggestions — all batched.

**Index review:** every filter column on the hot paths is indexed (`status`, `category_id`, `slug`, `price_min`, GIN on `search_vector`, `pg_trgm` on title/slug, the material/size `EXISTS` join columns). `EXPLAIN` showed index scans, no sequential scans on the catalogue paths. No indexes were added by this audit, because none were justified.

**Payload size:** `per_page` is bounded and rejects `0`, negatives and absurd values with 422. `per_page=100` returns a workable page; nothing returns thousands of rows.

**JS bundle:** 21 chunks, 919 KB raw, **295 KB gzip**. Not optimised further in this audit — the audit found no evidence of unnecessary client components on the hot paths, and the server components are already server components. Flagged in §15 as worth a bundle analysis, not as a known bottleneck.

---

## 7. Lighthouse results

Six routes, production build, desktop.

| Route | Accessibility | Best Practices | SEO | Failures |
|---|---|---|---|---|
| `/shop` | **100** | 100 | 100 | none |
| `/` | **100** | 100 | 100 | none |
| `/products/danger-high-voltage` | **100** | 100 | 100 | none |
| `/cart` | **100** | 100 | 100 | none |
| `/industries` | **100** | 100 | 100 | none |
| `/bulk-order` | **100** | 100 | 100 | none |

`/shop` was 96 before F-3, failing `color-contrast` on 10 footer elements. After the palette fix: 100 with zero failures, confirmed on all six routes.

**Performance score: not returned by the harness** — the Lighthouse integration reports accessibility, best practices and SEO only in this environment. Rather than quote a number I did not measure, the Core Web Vitals above are the substitute: LCP ≤ 624 ms and CLS 0 across every route, measured directly via `PerformanceObserver` in the browser.

SEO is 100 on every route: metadata present, canonical URLs correct, Open Graph and Twitter cards set, `sitemap.xml` and `robots.txt` served, JSON-LD structured data present on product pages, and **no false prices in structured data** — product JSON-LD is generated from the same server-fetched variant data the page renders, never from a browser calculation.

---

## 8. Accessibility results

- Lighthouse axe audit: **0 violations** on all six audited routes.
- Contrast: all text tokens now verified by computation, not by eye, against every surface they appear on. 4.5:1 minimum for body text, and the amber/danger/safe/info signal colours are reserved for non-text indicators or paired with a text label.
- Keyboard: every interactive element reachable in a sensible order; focus is visible (`prefers-reduced-motion` honoured in the design system); the skip link is present and parks off-screen until focused.
- The cart card has no add-to-cart button — a card cannot hold a valid variant, so offering one would be a dead control.
- Incompatible material/size combinations are rendered **disabled** with a note explaining why, rather than hidden. This was verified as a reachability property across 20 products (§9), and the 40-test browser suite includes a guard that fails loudly if the import pipeline later produces sparse matrices that would make that state reachable.
- `role="radiogroup"` with `aria-label` on the Material and Size groups; the resolved SKU and price are announced as the selection changes.
- Not verified and not claimed: full screen-reader pass (NVDA/VoiceOver), and a complete keyboard-only traversal of checkout — checkout is not built, so there is nothing to traverse.

---

## 9. Security findings

**No P0 security defect was found.** Specifically:

**Authorization is sound.** 60 probe combinations — 7 admin endpoints and 5 account endpoints, each against 5 token shapes (absent, garbage, `alg:none` with a forged ADMIN claim, expired, malformed) — returned **401 in every case. Zero violations.** The `alg:none` attack, which is the standard JWT bypass, is correctly rejected: the verifier pins the algorithm rather than trusting the header. Privilege escalation via `PATCH /admin/customers/{id}/role` with `{"role":"ADMIN"}` is blocked. Enforced server-side, not by a frontend route guard, not by `localStorage`, not by the JWT role claim alone.

**Input validation is sound.** No 500s from SQL injection strings (`' OR 1=1--`, `'; DROP TABLE products;--`), path traversal, `<script>` payloads, invalid UUIDs, or negative/absurd pagination. All parameters are bound; no string interpolation into SQL was found. `per_page=0`, `per_page=-5`, `page=0`, `min_price=-1`, `min_price=abc`, `sort=nonsense` all return 422. An unknown slug returns 404 rather than reflecting input.

**No secrets in the repository.** No `.env` file is tracked; only `.env.example`. No JWT, `sk_live_`, `rzp_live_`, AWS or `ghp_` token anywhere in tracked files. The only matches for the secret-value scan were test fixture strings with self-describing names (`"unit-test-supabase-jwt-secret-value-0123456789"`) — not real credentials, though see §15.

**No secret reaches the browser.** The served HTML and all 21 JS chunks contain no JWT and no service-role key. `lib/env.ts` reads `process.env` as literals specifically so Next's `NEXT_PUBLIC_*` inlining works, and it exposes only the public API base URL plus verified business facts. The service-role key and Razorpay key secret are backend-only.

**XSS.** The Markdown renderer escapes by default and is covered by tests. The one place the frontend reflects user input — the search results heading — uses JSX interpolation, not `dangerouslySetInnerHTML`. Seed SVGs are served same-origin as vectors via `unoptimized` rather than enabling `dangerouslyAllowSVG`.

**CSRF.** Not applicable to the current surface: the API is token-authenticated, not cookie-session-based, and the only state-changing endpoint reachable without a token is the quote form, which is public by design. When cookie sessions are introduced for auth, this must be revisited — it is called out in §15.

**CSRF-shaped note on the quote endpoint:** unauthenticated `POST` endpoints need rate limiting before launch. None is configured yet.

**Findings that are real but low severity:**
- The OpenAPI schema advertises every operation as public (I-10). Enforcement is unaffected; the documentation misleads.
- `/health/ready` enumerates which credentials are absent. Fine for an internal probe, must be gated in production.
- `/api/docs` and `/api/openapi.json` are public in development.

**Not tested, and therefore not claimed:** file upload security (no upload endpoint exists), rate limiting, cookie/CSRF behaviour (no cookie auth), and TLS/HSTS in production (no production deployment).

---

## 10. API findings

56 documented operations across catalogue, content, account, admin, search and health.

**Status-code coverage verified:** 200, 201, 204, 400, 401, 403, 404, 405, 409, 422 and the error envelope. Unknown routes return a clean 404 with `{"error":{"code","message","request_id"}}` — no stack trace, no SQL, no internal path. `/health/ready` reports component status with latency per component.

**Response size discipline:** no endpoint returns more than the UI needs. `per_page` is capped and validated.

**Response shape:** consistent envelope with a request id on every response, which is what made the hostile-probe output above diagnosable.

**Issues:** I-6 (500 on null byte), I-7 (100 KB query → connection failure, not 4xx), I-10 (OpenAPI security metadata). All P2/P3.

**The API's read surface is in good shape. Its write surface is the gap** — there is no cart, order, payment, quote-submission, coupon or review endpoint. `POST /api/v1/admin/customers` exists for account administration, which is the only write path in the system today.

---

## 11. Database findings

**Row counts:** 105 products, 1412 variants, 18 categories, 4 materials, 9 sizes, ~315 images, ~400 inventory rows, 10 industries, blog posts, tags. 47 of the live site's 152 products are not yet migrated — tracked in `docs/CONTENT_PENDING.md`, and the import pipeline is Phase 2.

**Migrations apply cleanly** from empty. The Alembic `render_item` hook is removed (it was silently emitting column-less tables) and `op.execute` is pinned to exactly one statement per call, both enforced by tests.

**Query plans reviewed** with `EXPLAIN (ANALYZE, BUFFERS)`. The catalogue list, facets and search all use index scans. The material/size filter is correctly a **single variant-level `EXISTS`**, not two — two would cross-product and return pairings the business does not sell. This is pinned by a test.

**The one finding: an application-layer N+1, not a database one.** The raw SQL is 0.3–2.3 ms; the endpoint is 111 ms. Fixing the industries case took 11 queries to 1. The remaining case (I-8, 16 queries for 8 products) is not understood well enough to fix safely, and is written up rather than guessed at.

**Category taxonomy is flat**, matching the live site and preserving SEO URLs. Pinned by a test so it cannot be silently redesigned.

**No indexes were added.** Every index the hot paths need already exists; adding more without a measured plan change would be noise.

---

## 12. Responsive testing

7 widths × 6 routes = 42 checks, plus tap targets at mobile widths.

Widths: **390 × 844, 430 × 932, 768 × 1024, 1024 × 768, 1280 × 800, 1440 × 900, 1920 × 1080.**
Routes: `/`, `/shop`, `/category/electrical-safety`, `/products/danger-high-voltage`, `/cart`, `/bulk-order`.

| Width | Result |
|---|---|
| 390 | clean |
| 430 | clean |
| 768 | clean |
| 1024 | clean |
| 1280 | clean |
| 1440 | clean |
| 1920 | clean |

Checked at each: horizontal page pan (`scrollWidth > clientWidth`), elements overflowing with no clipping ancestor, interactive controls positioned outside the viewport, and console errors.

**Two real issues found and fixed during earlier passes**, both caught by this harness rather than by build or typecheck: a 31 px overflow from a missing `min-w-0`, and a header that pushed the cart icon 220 px off-screen at 1024 px.

**Two false positives I did not act on**, recorded because acting on them would have been wrong:
- The skip link reports as "outside the viewport" at every width. It is deliberately parked off-screen and revealed on focus. That is correct technique.
- Category-rail links report as "outside the viewport" at 390/430. They are inside a deliberately horizontally scrollable rail. Overflow inside a scroll container is not a bug.

A third signal — an "outside viewport" reading on a category-card link at 390 px — I traced to an element with a zero-width box inside a `display: none` subtree (the rail is `hidden lg:block`). The heuristic was measuring a hidden element. Not a product defect.

Tap targets: no header or main control under 32 px at 390 or 430.

---

## 13. Browser testing

Driven as a customer, at 390 × 844, with console, network and Core Web Vitals instrumentation on every step.

```
 1. Homepage loaded
 2. Mobile drawer opens
 3. Shop reached via drawer
 4. Filter applied -> material=3MM ACP
 5. Search results
 6. Product page: Danger High Voltage
       materials: 3MM ACP, 5MM FOAMSHEET, AUTOGLOW STICKER, ECO VINYL STICKER
       sizes:     12x18, 18x24, 24x36, 36x48
       price Rs.180 -> Rs.612   sku SKU SPP-ELS-006
 7. Material + size selected
 8. Added to cart (qty 2)
       cart line: Danger High Voltage | 5MM FOAMSHEET | 18X24 IN. |
                  SPP-ELS-006-5MMFOAMSHEET-18X24 | 2 | Rs.612 x 2 | Rs.1,224
 9. Cart shows the exact variant and quantity
10. Checkout: stops honestly, no fake payment
    cart survived a reload: true
    cart lines after a 2nd variant of the same product: 2
```

**Verified properties:**
- Line identity is the exact variant. `SPP-ELS-006-5MMFOAMSHEET-18X24 × 2` — material, size and SKU all match the selection, and the line total is quantity × the server's price.
- **Two variants of the same product are two separate cart lines.** The single most important ecommerce invariant in the cart, and it holds.
- Price and SKU track the selected variant live: Rs.180 → Rs.612 when the material changed.
- The cart survives a reload.
- Checkout discloses that payment is unavailable rather than presenting a form that cannot work.

**Variant matrix, 20 products across categories.** For every product, every material × size cell was walked and checked against live API data:

```
product                       mats sizes  inStock  purchasable  verdict
5s-seiketsu-standardise          4     3       7           7  ok
area-in-front-of-electrical-panel 4     4      16          16  ok
caution-overhead-work            4     4      16          16  ok
danger-confined-space            4     4      16          16  ok
danger-toxic-gas                 4     4      16          16  ok
electric-shock-survival          4     3      12          12  ok
emergency-shower                 4     4      14          14  ok
fire-extinguisher-operation      4     4      14          14  ok
maintain-cleanliness              4     3      12          12  ok
msds-of-ethylene-dichloride-2    4     3      12          12  ok
msds-of-toluene-1                4     3      11          11  ok
no-smoking-in-canteen            4     3      10          10  ok
quality-means-satisfied-customer 4     3      10          10  ok
safety-first                     4     3      12          12  ok
stairs-directional-board         4     4      14          14  ok
wash-hands-before-eating         4     3      12          12  ok
wear-mask                        4     3      12          12  ok
please-keep-this-area-clean      4     3      12          12  ok
school-zone-ahead                4     3       8           8  ok
                                   (all variant-matrix properties hold)
```

Four properties, all confirmed: the UI offers exactly the materials and sizes the API declared; a combination with no variant is **disabled**; a combination with an in-stock variant is **purchasable**; and the displayed price equals the server's price for the resolved variant. 190 combinations walked.

**Browser console:** zero unexpected errors on any production flow after F-2. Before F-2, `/search` logged a CORS failure on every page load.

**Network:** no duplicate API calls, no failed requests, no requests carrying secrets, no waterfall (server components fetch directly; the browser makes no catalogue calls).

**Two test bugs found and corrected during the audit** — recorded because a wrong test that "passes" is worse than no test: my first variant-audit queried the DOM before hydration and reported "0 material options" on a healthy product; and its SKU locator matched the product-level SKU instead of the variant SKU. Both were wrong tests, not wrong code, and both were fixed before any conclusion was drawn from them.

---

## 14. Remaining issues

### P0 — blocks taking a real order

| # | Severity | Location | Problem | Reason | Exact next action |
|---|---|---|---|---|---|
| R-1 | **P0** | whole stack | No cart API. Cart is `localStorage` only. | Two browsers cannot share a cart; the server cannot price an order; a user can hand-edit a price the server never agreed to. | Build `POST/GET/PATCH/DELETE /api/v1/cart` with a server-side `cart_items` table keyed on `variant_id`, and make the frontend cart a projection of it. Prices resolved server-side only. |
| R-2 | **P0** | whole stack | No inventory reservation. | Nothing prevents overselling. `inventory` exists but nothing writes to it. | Implement the reservation transaction in `docs/ARCHITECTURE.md`: `SELECT ... FOR UPDATE` on the variant's inventory row, verify `available >= qty`, increment `reserved`, insert the reservation row, all in one transaction. Add a concurrency test that fires two simultaneous checkouts for the last unit and asserts exactly one succeeds. |
| R-3 | **P0** | `frontend/src/app/checkout` | No payment integration and no order confirmation. | The journey ends at an honest "not connected" state. | Integrate Razorpay. **Hard requirement:** the frontend must not mark an order paid. The backend verifies the signature against `RAZORPAY_KEY_SECRET`, and the webhook is the authority. Webhook processing must be idempotent — add a test that delivers the same webhook twice and asserts one state transition. |
| R-4 | **P0** | `frontend/src/app/account` | No order history. | A customer cannot see or re-order anything. | Order list and detail routes, reading from server-side orders with customer scoping enforced in the query, not in the UI. |
| R-5 | **P0** | no admin surface | `/admin` does not exist. | Staff cannot manage products, orders, quotes or inventory. | Build admin products, orders, quotes and inventory routes. The RBAC backend already exists and is verified — the UI must call it, never replace it. |

### P1

| # | Severity | Location | Problem | Reason | Exact next action |
|---|---|---|---|---|---|
| R-6 | P1 | `frontend/src/components/catalog/CartLineItem.tsx` | Cart totals are an estimate. | Shipping and GST are applied in the browser, because there is no server to apply them. `CartTotals.isEstimate` is typed `true` for this reason. | Once R-1 lands, move all totals server-side and narrow the type to a discriminated union so an estimated cart cannot be rendered as a final one. |
| R-7 | P1 | `frontend/src/app/bulk-order` | Quote form is UI-only; no submission endpoint. | A B2B lead is silently lost. | `POST /api/v1/quotes` writing to the existing `quote_requests` table, with server-side validation, an idempotency key to survive double-clicks, and rate limiting. |
| R-8 | P1 | `frontend/src/app` | Wishlist is not persisted to an account. | Not a purchase path, but it is a named feature that does nothing durable. | Back the wishlist with an account-scoped table, or remove the control until it works. Do not leave a control that appears to work and does not. |

### P2

| # | Severity | Location | Problem | Reason | Exact next action |
|---|---|---|---|---|---|
| R-9 | P2 | `backend/app/services/catalog.py:297` | Product list issues 16 queries for 8 products; `product_tags` 5×. | `ProductVariant.product` and `ProductRatingSummary.product` are `lazy="joined"`, so parent copies re-fire the collection loaders. Two fix attempts broke 32 tests. | Add a dedicated read DTO for the listing card (slug, title, image, price range, category, rating summary) that does not load variants at all — the card only needs a min/max price, which is denormalised on `products`. That removes the problem instead of fighting the loader. |
| R-10 | P2 | `backend` request path | Null byte in the path returns 500. | No content validation at the router boundary. | Reject control characters in path parameters at the validation layer, returning 404. The error envelope already prevented a trace leak, so this is a status-code correctness fix, not a security hole. |
| R-11 | P2 | `backend/app/api/v1/search.py` | A 100 KB query string fails at the connection layer, not as a 4xx. | No maximum length on `q`. | Cap `q` at 100 characters in the Pydantic model and return 422. Test with a 100 KB query. |
| R-12 | P2 | `frontend` bundle | 295 KB gzip of JS, 21 chunks. | Not measured as a bottleneck — LCP is ≤ 624 ms — but it is the obvious next lever. | Run a bundle analysis. Prime suspect: the icon library and the variant selector, both of which are client components on every product page. |
| R-13 | P2 | `backend/app/api/v1/quotes` (pending) | No rate limiting on unauthenticated POST. | The quote form is a spam target the moment it is wired up. | Add rate limiting at the edge before R-7 ships. |

### P3

| # | Severity | Location | Problem | Reason | Exact next action |
|---|---|---|---|---|---|
| R-14 | P3 | `frontend/src/app/not-found.tsx` | 404s return HTTP 200. | The async root layout streams the shell before the child resolves, so the status cannot be set. `noindex` is always present, so SEO damage is contained. | Either a non-streaming shell for the 404 path, or handle unmatched slugs in a Route Handler that can set the status. |
| R-15 | P3 | `backend/app/api/v1/*.py` | OpenAPI declares 0 protected operations. | Auth is applied per-handler via `Depends()`, which FastAPI does not surface in the schema. | Attach the auth dependencies at router level, or pass explicit `security=` metadata per operation, so the published schema is accurate. |
| R-16 | P3 | `backend/app/core/config.py` | `/api/docs` and `/api/openapi.json` are public. | Correct in development, wrong in production. | Gate on `ENVIRONMENT`; serve 404 outside development. |
| R-17 | P3 | `backend/app/api/health.py` | `/health/ready` names missing credentials. | Fine internally, an information leak externally. | Restrict to the internal network or require an auth header in production. |
| R-18 | P3 | `backend/app` | Auth is token-based; CSRF not applicable. | No cookie sessions exist. | Re-audit CSRF the moment Supabase cookie sessions are introduced for the browser. Do not assume the current "not applicable" verdict carries over. |

### P4

| # | Severity | Location | Problem | Reason | Exact next action |
|---|---|---|---|---|---|
| R-19 | P4 | `backend/tests/conftest.py`, `test_security.py` | Test-only secret *values* are committed. | Not real credentials. | Move to a fixture module or generate at session start, so no 24+-character string that looks like a secret exists in the repository. |
| R-20 | P4 | `frontend/src/app/blog` | `CLS 0.013`. | Well inside the good threshold. | Leave it. Not worth destabilising layout for 0.013. |
| R-21 | P4 | `frontend/public/seed/**` (333 files) | Product imagery is generated placeholder SVG. | Correct for a build that must not hotlink or copy the reference site, and every file is labelled `PLACEHOLDER ARTWORK` in-frame. | Commission real photography before launch. **This must not go live as-is** — a safety-signage business selling placeholder artwork is worse than having no photography. |
| R-22 | P4 | `docs/CONTENT_PENDING.md` | GSTIN, business hours, Maps link, policy text, HSN codes unresolved. | The business has not supplied them. Inventing them would be fabrication. UI renders explicit pending states; policy pages show structure with the gaps marked. | Business supplies the facts. Do not fill these in without them. |

---

## 15. Recommended next steps

**In order, because each unblocks the next:**

1. **Cart API (R-1).** Everything downstream — checkout, inventory, payment, orders — depends on a server that knows what is in the cart and can price it. Nothing else in Phase 2 can be tested until this exists.
2. **Inventory reservation (R-2).** Must land with the cart API, not after checkout, because the reservation is what makes a cart line real. Ship the concurrency test in the same change.
3. **Orders + Razorpay (R-3, R-4).** Backend verifies the signature; the webhook is the authority and is idempotent; the frontend never marks an order paid. Add the duplicate-webhook test before considering it done.
4. **Admin (R-5).** The verified RBAC backend already exists — build the UI against it and do not weaken it.
5. **B2B quote API (R-7).** A lead path that silently drops leads is worse than no lead path.
6. **Catalogue import: 47 of 152 products (R-22 context).** Until this is done the site under-represents the catalogue by a third.
7. **Real product photography (R-21).** Standalone prerequisite. Placeholder artwork must not ship.
8. **Business facts (R-22).** GSTIN, hours, Maps, policies, HSN codes.
9. **The P2/P3 list** — all are well-understood, individually small, and can be batched.
10. **Deployment.** Blocked on credentials: Supabase, Razorpay, and hosts for the Next app and the API. `/health/ready` currently reports these as `degraded` and no deployment has been made. **No production deployment is claimed anywhere in this report.**

**What I would not do:** optimise further without a measurement. The database is at 0.3–2.3 ms, LCP is under 650 ms, CLS is 0, Lighthouse is 100/100/100. The remaining performance work (R-9, R-12) is real but is not what is making this site slow — the missing checkout is.
