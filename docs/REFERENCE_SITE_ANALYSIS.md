# Reference Site Analysis — safetyposterprint.com

Analysis date: 2026-09-27
Reference: `https://www.safetyposterprint.com/`
Purpose: business, catalogue and content reference for the rebuild.

> **Status of this document.** Everything marked **Verified** was read directly
> from the public site on the analysis date. Everything marked **Unverified** was
> *not* found and must be supplied by the business owner. Nothing unverified has
> been invented anywhere in this repository — see
> [`docs/CONTENT_PENDING.md`](./CONTENT_PENDING.md).

---

## 1. What the existing site is

A Wix-hosted single-page-application storefront selling **industrial safety
signage, posters and boards** to factories, plants, offices, laboratories and
commercial buildings across India.

**Verified business identity**

| Field | Value |
|---|---|
| Trading name | Safety Poster Prints |
| Self-description | "India's #1 Safety Posters Store" |
| Sub-line | "High-Quality Safety Posters for Industries, Offices & Workplaces – Durable, Laminated & Ready to Install." |
| Address | GF-40, 41, 42, Real Square, Ankleshwar – Valia Rd, opp. Sanatan School, GIDC, Ankleshwar GIDC, Ankleshwar, Kosamdi, Gujarat 393002 |
| Email | safetyposterprint@gmail.com |
| Phone | +91 83200 50573 |
| Instagram | [@safetypostersprint](https://www.instagram.com/safetypostersprint) |

**Unverified — must be supplied by the business, not guessed**

| Field | Why it matters | Status |
|---|---|---|
| GSTIN | Required for GST invoices and B2B checkout | **Not published on the site** |
| Business hours | Footer / contact page | **Not found** |
| Google Maps / location URL | Contact page | **Not found** |
| Years in business / team size / client count | About page claims | **Not stated on the site** |
| Shipping charges, courier partners, delivery SLA | Shipping policy | Page exists, not read |
| Return window and conditions | Refund policy | Page exists, not read |

These are listed in `docs/CONTENT_PENDING.md` with the exact placeholder text
the frontend renders in their absence, so the site never publishes a fabricated
figure.

---

## 2. Navigation

**Header (existing)**

```
[announcement strip]  Home · Shop · About · Blog · Wish List  ·  Search  ·  log in
```

**Footer (existing)**: Shop, About, Blog, Policy (Terms, Privacy, Refund,
Shipping), Contact (address, email, phone), social.

**Problem with the current navigation**

* "Catagories" is misspelled in the desktop nav and the mobile drawer.
* The category list is rendered as one flat 18-item block in **four** places
  (desktop nav, mobile drawer, footer, and a third partial list). It is
  duplicated markup, not a shared data source, so it drifts.
* "Industries" and "Contact" do not exist as pages, despite being the two things
  a B2B buyer is looking for.
* There is no cart page link in the header — only "Add to Cart" buttons.

**What the rebuild does**

* One category source of truth (the database), rendered into a mega-menu on
  desktop and a drawer on mobile.
* Nav becomes: **Products · Categories · Industries · 5S · About · Contact**,
  plus Search, Account, Wishlist, Cart.
* Fixes the "Catagories" spelling.

---

## 3. Category structure — **Verified, 18 categories**

Slugs below are the **existing, live** slugs and are preserved so that SEO
equity and existing inbound links survive the migration.

| # | Display name | Existing slug | Notes |
|---|---|---|---|
| 1 | MSDS | `msds` | 52 products, ₹320–₹9,000 |
| 2 | PPE | `ppe` | |
| 3 | Caution Signages | `caution-signages` | |
| 4 | Danger Signages | `danger-signages` | |
| 5 | 5S Methodology | `5s-methodology` | Has a dedicated collection section |
| 6 | Electrical Safety | `electrical-safety` | 10 products, ₹80–₹8,800 |
| 7 | Directional Signages | `directional-signages` | |
| 8 | Emergency Signages | `emergency-signages` | |
| 9 | Environmental Signages | `envirnomental-signages` | ⚠️ slug is misspelled on the live site. **Slug preserved**; display name corrected. A `301` from the corrected spelling is served. |
| 10 | Health Safety | `health-safety` | |
| 11 | Fire Safety | `fire-safety` | |
| 12 | Motivational Signages | `motivational-signages` | |
| 13 | Lab Safety | `lab-safety` | |
| 14 | Office Signages | `office-signages` | |
| 15 | Quality & Productivity | `quality-productivity` | |
| 16 | Road Safety | `road-safety` | |
| 17 | Canteen | `canteen` | |
| 18 | Outdoor Pylon Signage Board | `pylon-boards` | slug does not match the title |

Two additional pseudo-categories exist: `all-products` and `best-sellers`. In
the rebuild these become **sort modes**, not categories, because they are views
over the catalogue rather than taxonomy.

> The live category pages also expose a sub-filter group containing
> "Warning", which duplicates the Caution/Danger taxonomy. The rebuild does not
> carry it forward; it is recorded here because it indicates an internal
> classification the business may still want as a tag.

---

## 4. Product structure

### 4.1 Shape of a product — **Verified**

URL pattern: `/product-page/{slug}`

A product page carries:

1. Title
2. Price
3. Short description (one or two lines)
4. **Size** selector (labelled "optional" on the live site)
5. **Add to Cart**, **Buy Now**, **Add to Wishlist**
6. An "IMPORTANT INFORMATION" block
7. Social share links

The "IMPORTANT INFORMATION" block is effectively the product's buying guide and
is **verbatim business copy worth keeping**:

> This product is available in multiple sizes, materials, and quantities.
> Please select Size, Material, and Quantity before adding the product to cart.
>
> **Available Materials:**
> - 3mm ACP Board – Durable & long-lasting
> - 5mm Foam Sheet – Lightweight & economical
> - Auto glow Sticker – Visible in darkness
> - Eco Vinyl Sticker – Waterproof & weather resistant
>
> **Size & Quantity:** Choose the size and quantity as per your workplace
> requirement. Bulk quantity pricing is available.
>
> **Pricing Notice:** Final price depends on the selected size, material, and
> quantity. Ensure all options are selected to view the correct price.

### 4.2 Materials — **Verified from the product page, 4 options**

| Value | Positioning from the site's own copy |
|---|---|
| `3MM ACP` | Durable & long-lasting |
| `5MM FOAMSHEET` | Lightweight & economical |
| `AUTOGLOW STICKER` | Visible in darkness |
| `ECO VINYL STICKER` | Waterproof & weather resistant |

`ACP` and `FOAMSHEET` also appear as bare labels in the filter UI. The rebuild
treats these as the same materials (the site uses them inconsistently) and
normalises them to a controlled vocabulary — see §9.

### 4.3 Sizes — **Verified from the project's product brief, 9 options**

`8x12`, `12x18`, `18x24`, `24x36`, `30x60`, `36x48`, `36x72`, `48x72`, `48x96`

Units are **inches**, applied as W×H.

### 4.4 Price model — **Verified by inference from two categories**

| Category | Lowest | Highest | Implied base |
|---|---|---|---|
| MSDS | ₹320 | ₹9,000 | ₹320 |
| Electrical Safety | ₹80 | ₹8,800 | ₹80 |
| All products | ₹0 | ₹9,000 | — |

Reading: the displayed price is the **cheapest variant** (smallest size, eco
vinyl), and the maximum is the same design in the largest size on the most
expensive material. So price is a function of **size × material**, not a single
flat price per product.

**Confirmed defect on the live site.** Large parts of the catalogue display
**₹0.00** on listing pages (all 16 "National Safety Week" posters, all three
Quality & Productivity posters). A ₹0 price in an ecommerce listing is both a
trust problem and an SEO problem. The rebuild never shows a zero price: every
product carries a real base price and displays "from ₹X".

### 4.5 Variants

A variant is the **cross product of Material × Size**, each with its own SKU,
its own price, and its own stock. This is the single most important structural
fact about the catalogue, and it maps directly onto the `product_variants` table
already built, using `attributes = {"Material": ..., "Size": ...}`.

Consequence: a 9-size × 4-material product is **36 variants**, each with its own
inventory row. This is exactly what the schema supports, and why stock
reservation has to be per-variant rather than per-product.

### 4.6 Catalogue size — **Verified**

**152 products** total across 18 categories. All Products page confirms
"152 products". Pagination is Wix "load more" (20 per page).

---

## 5. Product naming — **Verified samples**

Real product titles, captured for slug fidelity:

**Quality & Productivity**
- `NATIONAL SAFETY WEEK 16` … `NATIONAL SAFETY WEEK 1` (a 16-poster series)
- `Cost of Poor Quality (COPQ) Poster`
- `Quality Means Satisfied Customer Poster`
- `Stages of Quality Improvement Poster`

**Electrical Safety** (10, all base ₹80)
- `Electrical Safety Guide Multilingual`
- `Area In Front Of Electrical Panel`
- `Do Not Use Mobile Phones`
- `Electrical Shock Hazard Do Not Touch`
- `Electric Shock Survival`
- `Danger High Voltage`
- `Risk of Electric Shock` *(appears twice)*
- `Warning Electrical Hazard` *(appears twice)*
- `Warning – Electrical Hazard Safety Sign Board`

**MSDS** (52, all base ₹320) — chemical-specific safety data sheets
- Caustic Soda, Mono Ethyle Amine, DMSO, Bromine, Chlorine, Hexene,
  Thio Phenate Methyl, Toluene, Propionic Acid, OPDA, Ethylene Dichloride,
  N-Butanol, Tebu Oxirine, Tebuconazole, Methyl Cyclohexane, HCL,
  Cyanuric Acid, Dasda

**Data-quality defects found on the live site** (these are real, and the import
tool is built to catch them):

1. **Duplicate products.** `Risk of Electric Shock` and `Warning Electrical
   Hazard` each appear twice; `NATIONAL SAFETY WEEK 8` appears twice (once as
   `NATIONAL SAFETY WEEK8`, missing a space); `MSDS of Tebu Oxirine` and
   `MSDS of Thio Phenate Methyl` each appear twice with different slugs and the
   *same* image hash.
2. **Slug suffixes from Wix duplicates.** `msds-of-bromine-1`,
   `msds-of-chlorine-1`, `msds-of-hexene-1` — the `-1` suffix is a Wix artefact
   of creating a second product with the same name.
3. **Spelling errors in titles.** `NATIONAL SAFETY WEEK8`,
   `Envirnomental Signages`, `Mono Ethyle Amine` (vs. *Monoethylamine*),
   `Thio Phenate Methyl` (vs. *Thiophenate methyl*).
4. **Zero prices**, as above.

The rebuild normalises all four and reports each in an import audit rather than
silently dropping them.

---

## 6. Filters, sorting and search

### Existing
* **Filters:** Price (range), Material (multi), Size (multi)
* **Sort:** "Recommended" only
* **Search:** a Wix search box; no suggestion UI observed
* **Count:** shown ("152 products", "10 products")

### Gaps
* No Material/Size counts next to each option, so a shopper can pick a
  combination that returns nothing.
* Single sort option.
* No active-filter chips, no "clear all".
* No SKU or tag search.
* Mobile filters are the Wix default, not a designed drawer.

### Rebuild
* Filter by **Category, Price, Material, Size, Availability** — with live counts
  per option, computed in SQL over the current result set.
* Sort: Recommended, Newest, Price low→high, Price high→low, Best selling.
* Active filter chips + Clear all + a live "142 products" count.
* Search across title, SKU, category, tags, description, material and size, with
  debounced suggestions.
* Material and Size are **data**, not frontend constants — they are rows in the
  database, so the business can add `7MM ACP` without a deploy.

---

## 7. Cart, wishlist and account

**Verified:** "Add to Cart" on cards and PDPs, a wish list reachable only when
logged in (`/members-area/my/my-wishlist`), and a Wix members area.

**Not verified / weak:** the cart drawer/page behaviour, whether variants are
distinguished in the cart, and whether stock is checked. The live site's cart is
a Wix storefront cart whose variant handling could not be confirmed from the
markup.

**Rebuild requirements derived from the brief**

* Cart line = product + **material + size** + quantity. Different variants are
  never merged. *(The brief's own example: Electrical Hazard Board, 3MM ACP,
  18x24, qty 5.)*
* A persistent cart that survives sign-in.
* Wishlist persisted per customer.
* Guest checkout must be possible, or the funnel leaks — a factory supervisor
  ordering five boards is not going to register first.

---

## 8. Content: About, blog, policies

### Homepage (existing)
Hero → Products by Category → Best Sellers → Electrical Safety feature →
"Why Choose Us" (4 pillars: **Premium Print Quality**, **Expert Safety
Designs**, **Wide Material Options**, **Reliable & Professional Service**) →
footer.

The four "Why Choose Us" pillars are **verified business copy** and are carried
into the rebuild.

### Blog — **Verified, ~18 published articles**

Real titles, grouped by the themes the brief asks for:

| Theme | Articles |
|---|---|
| Chemical / multilingual | The Importance of Multilingual Chemical Safety Signage; The Role of Multilingual Safety Hazard Signs |
| PPE | 10 Reasons Your PPE Signage Isn't Working (And How to Fix It); PPE Signage: Why Your Visuals Might Be Failing Your Team |
| 5S | 10 Reasons Your 5S Methodology Posters Aren't Working (And How to Fix It) |
| Electrical | Are You Making These Common NEC 2026 Electrical Safety Sign Mistakes?; 15 Essential Electrical Safety Signs to Protect Your Team from High-Voltage Hazards |
| MSDS / hazcom | 5 Steps to Update Your MSDS Display Boards for 2026 OSHA Compliance |
| Warehouse | 15 Warehouse Safety Signs to Prevent Forklift Accidents and Pedestrian Collisions; 7 Mistakes You're Making with Your Warehouse Safety Signs; Why Everyone Is Talking About Proactive Warehouse Safety Signs |
| Construction | 15 Construction Safety Posters to Streamline Your Jobsite Compliance |
| Quality | 15 Quality and Productivity Posters to Boost Your Shop Floor Efficiency |
| Materials | Industrial Safety Sign Materials: A Guide to Choosing Between ACP, Foam Sheets, and Vinyl |
| Energy / environment | Why "Switch-Off" Visuals Will Change the Way You Manage Energy Costs; World Environment Day 2026 (×2) |
| Visual management | Why Visual Management Boards Will Change the Way You Track Productivity and Safety Metrics |
| Buying guide | The Safety Officer's Checklist: A Buying Guide for Factory-Wide Compliance |
| General | Do's and Don'ts: Workplace Safety Posters Guidance |

**Observations worth acting on**

* The blog is genuinely good and SEO-aligned. It is the business's best organic
  asset and the rebuild should preserve the URL slugs.
* Article format is consistently a numbered list ("15 …", "10 Reasons …",
  "5 Steps …", "7 Mistakes …") — deliberate and effective for this audience.
* Two articles cite **2026 regulatory content**: NEC 2026 electrical sign
  changes, and OSHA HazCom / GHS Rev 7 with a **19 July 2026** compliance
  deadline. These are the highest-value content on the site and should anchor the
  rebuilt blog.
* Author names are not displayed. **Unverified** — must not be invented.

### Policies
`/terms-and-conditions`, `/privacy-policy`, `/refund-policy`, `/shipping-policy`
all exist. Content not read; must be supplied/approved by the business rather
than rewritten by us.

---

## 9. Migration plan

### 9.1 Data model mapping

| Existing concept | Target table | Notes |
|---|---|---|
| Category | `categories` | 18 rows, slugs preserved verbatim |
| Product | `products` | title, slug, description, base_price, category |
| Product price | `products.base_price` | real base price, never 0 |
| Material × Size option | `product_variants.attributes` | `{"Material": "3MM ACP", "Size": "18x24"}` |
| Variant price | `product_variants.price_override` | computed from size × material |
| Variant stock | `inventory` (per variant) | one row per variant |
| Product image | `product_images` | `storage_path` → Supabase Storage |
| Wishlist | `wishlists` / `wishlist_items` | variant-level |
| Cart | `carts` / `cart_items` | variant-level, never merged |
| Best sellers | derived from `order_items` | no stored counter |
| "Recommended" | derived (featured + rating + recency) | not a stored flag |
| Blog | `blog_posts` / `blog_categories` | new tables |
| Industry pages | `industries` / `industry_products` | new tables |
| Bulk enquiry | `quote_requests` | new table |
| Contact form | `contact_messages` | new table |
| GST / B2B fields | `orders.*` | gstin, company_name, po_number, taxable_amount, tax_amount, invoice_number |

### 9.2 Import pipeline

```
   Wix CSV export  ──or──  manual catalogue sheet
              │
              ▼
   scripts/import_products.py        (pure Python, no network)
              │  normalise name · normalise category
              │  normalise material · normalise size
              │  normalise price · generate slug
              │  detect duplicates · validate
              ▼
   data/import/products.normalised.json  +  import-report.json
              │
              ▼
   python -m app.scripts.seed --from data/import/products.normalised.json
              │
              ▼
   Supabase PostgreSQL
```

**Deliberately not a scraper.** The runtime must never depend on the old site,
and the import must be reproducible. A Wix CSV export (Wix → Settings → Data →
Export) or a spreadsheet the business maintains is the correct input, because:

* it is complete — 152 products, not 20 that a crawler happened to reach;
* it is a one-off — no scheduled dependency on a third party;
* it is auditable — the normalised JSON is reviewable before it touches a
  database.

`scripts/import_products.py` therefore reads a **local file** and performs
normalisation and validation. It additionally offers a `--from-url` mode for
*one-off research only*, clearly marked as not for production.

### 9.3 Image migration

| Step | Action |
|---|---|
| 1 | Business owner confirms image ownership. Wix-hosted images are the business's own uploads and are expected to be, but this **must be confirmed in writing**. |
| 2 | Download originals to `data/import/images/`. |
| 3 | Upload to Supabase Storage under `products/<category>/<sku>-<n>.webp`. |
| 4 | Store the **path** in `product_images.storage_path`; the API mints short-lived signed URLs. |
| 5 | Anything unconfirmed is seeded as a **generated placeholder** and listed in `data/import/placeholder-manifest.json` so it is impossible to ship by accident. |

`product_images.url` never points at `static.wixstatic.com`. The live site's
image URLs are all CDN derivatives of Wix-owned media, and hotlinking them
would make the rebuild depend on a third party and would not survive a Wix plan
change.

### 9.4 SEO preservation

| Existing URL | New URL | Action |
|---|---|---|
| `/category/{slug}` | `/category/{slug}` | 301, slugs unchanged |
| `/category/all-products` | `/shop` | 301 |
| `/category/best-sellers` | `/shop?sort=best_selling` | 301 |
| `/product-page/{slug}` | `/products/{slug}` | 301 per product |
| `/post/{slug}` | `/blog/{slug}` | 301 per article |
| `/` | `/` | — |
| — | `/industries/{slug}` | new |
| — | `/5s` | new |
| — | `/bulk-order` | new |

A generated redirect map (`data/import/redirects.csv`) is emitted by the import
so the migration can be uploaded to the host in one step. Slug collisions caused
by the duplicate products (§5) are resolved in favour of the **lower** existing
slug, with the discarded one 301'd to the survivor.

---

## 10. Migrate vs. redesign

### Migrate as-is (business data)
* 18 category names and slugs
* Product titles and slugs
* Material vocabulary and its four positioning descriptions
* Size vocabulary
* Price points and the size × material model
* Business name, address, email, phone, Instagram
* "Why Choose Us" four pillars
* Blog titles, slugs and themes
* Policy page existence

### Redesign (implementation)
* Everything visual. The Wix layout is not a design reference.
* Header/footer structure and the four-times-duplicated category list
* "Catagories" → "Categories"
* Filters: add counts, availability, active chips, clear-all
* Sort: add Newest, Price ↑/↓, Best selling
* Search: add SKU, tag, material, size; add suggestions
* Cart: variant-aware, persistent, guest-capable
* Pricing display: never show ₹0; show "from ₹X"
* Add **Industries**, **5S**, **Bulk Order**, **Contact** as first-class pages
* Add GST/B2B checkout fields and a quote workflow
* Fix the duplicate and misspelled catalogue records
* Replace Wix "load more" with real pagination

### Add (new capability)
* Bulk quote workflow (`quote_requests`) with admin management
* Industry landing pages
* 5S collection with per-step educational content
* GST-ready invoicing
* Server-authoritative pricing, stock and tax
* Full staff admin dashboard
* Real background jobs, audit log, structured logging

---

## 11. Explicit non-goals

* Not copying Wix source, markup or CSS.
* Not an iframe or a visual skin over the old site.
* Not depending on `safetyposterprint.com` at runtime, for any purpose.
* Not hotlinking Wix CDN images.
* Not inventing GSTIN, business hours, founding year, staff count, client count,
  certifications or customer testimonials.
* Not fabricating reviews. The seed ships with **zero** reviews and zero
  testimonials; the review system is fully built and simply starts empty.

---

## 12. Outstanding research

To complete the rebuild, the business owner should supply:

1. **Wix CSV export** or catalogue spreadsheet (all 152 products, with variant
   matrices and prices) — or explicit approval to seed the representative
   subset described in `docs/CONTENT_PENDING.md`.
2. **GSTIN**, for GST invoices.
3. **Business hours**.
4. **Google Maps** link for the Ankleshwar address.
5. **Text of the four policy pages**, for legal review before launch.
6. **Confirmation of image ownership**.
7. **Shipping matrix** — courier, rates by pincode, free-shipping threshold, and
   whether large ACP boards ship differently from A4 stickers.
8. **Bulk pricing tiers**, if the site does not already define them.
