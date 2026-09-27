# Content pending — must be supplied by the business

**Nothing in this list has been invented anywhere in the repository.** Where a
value is missing, the frontend renders an explicit "not yet confirmed" state or
omits the element, and the API returns `null`. That is a deliberate choice: a
fabricated GSTIN on a tax invoice, or an invented founding year on an About page,
is a legal and reputational problem that is much worse than a blank field.

Last reviewed: 2026-09-27

---

## 1. Blocking for launch

| # | Item | Why it blocks | Where it appears | Status |
|---|---|---|---|---|
| 1 | **GSTIN** | Required on a GST invoice. A business order without it cannot be invoiced correctly. | checkout, invoice, `orders.gstin` | ❌ not published |
| 2 | **Full catalogue export** | 105 of 152 products are seeded from the public catalogue. The remaining 47 are not represented. | `products` | ⚠️ partial |
| 3 | **Shipping matrix** | Courier name, rates by pincode/weight, free-shipping threshold, and whether large ACP boards ship differently. Our seeded figures are placeholders. | `shipping_methods` | ❌ not published |
| 4 | **Policy page text** | Terms, Privacy, Refund and Shipping pages exist on the live site but are legal text that we must not rewrite. | `/policies/*` | ❌ not read |
| 5 | **Image ownership confirmation** | Confirms the right to use the existing product artwork. | all `product_images` | ❌ not confirmed |

## 2. Blocking for a complete rebuild

| # | Item | Notes | Status |
|---|---|---|---|
| 6 | **Business hours** | Not on the live site. Contact page and footer. | ❌ |
| 7 | **Google Maps URL** | The address is verified; a maps link is not published. Contact page. | ❌ |
| 8 | **Bulk pricing tiers** | Volume discount structure for ACP, foam sheet and pylon boards. Affects the quote workflow. | ❌ |
| 9 | **Author attribution for blog posts** | The live blog shows no author. We will not invent one. | ❌ |
| 10 | **Real product reviews** | The live site publishes no verifiable reviews. The system ships with **zero** reviews and a proper empty state. See §4. | ❌ |
| 11 | **HSN/SAC codes per product** | Seeded with `4911` (printed matter) for all products. Real codes vary by material. | ⚠️ default |
| 12 | **Social profiles** | Instagram is verified. No Facebook, LinkedIn or YouTube links are published. | ⚠️ partial |

## 3. Nice to have

| # | Item | Status |
|---|---|---|
| 13 | Customer logos / client list | ❌ not published |
| 14 | Certifications held (ISO, etc.) | ❌ not published |
| 15 | Years in business, team size | ❌ not published |
| 16 | Warranty / replacement terms for signage | ❌ not published |

---

## 4. Deliberately not invented

These are the things an AI-generated ecommerce site normally fills in, and which
this rebuild refuses to:

* **Testimonials** — the live site has none. `TESTIMONIALS` was removed from the
  seed entirely. A testimonial section renders an empty state until genuine,
  attributable reviews are supplied.
* **Review counts and star ratings** — seeded at zero. There is a test
  (`TestNoFabricatedSocialProof`) that fails if any product shows a non-zero
  rating, so this cannot regress silently.
* **"India's #1"** — this phrase *is* the business's own self-description and
  appears in the analysis, but it is **not** used as an unqualified claim in
  new marketing copy, because an unverified superlative is a liability.
* **Customer counts, order counts, years in business** — not published.
* **Google reviews rating** — not published.

---

## 5. How the seed handles the partial catalogue

The seeded catalogue is **not** presented as the complete product range. It
exists to make the application fully functional and demonstrable:

* 18 of 18 categories are present, with their **exact live slugs**, so the IA
  and SEO equity carry over.
* 105 products spanning every category, with real product titles taken from the
  public catalogue where they are verifiable.
* 1,412 variants from the real Material × Size matrix.
* Product copy is **original**, written for this rebuild. It is not copied from
  the live site, which is the business's own copy and may be edited by us as
  owner but must be authored deliberately.

To complete the catalogue, see `docs/REFERENCE_SITE_ANALYSIS.md` §9.2 for the
import pipeline. The input is a Wix CSV export or a spreadsheet the business
maintains — **not** a scraper.

---

## 6. Placeholder assets

All 315 seeded product images are **generated SVG placeholders**, written by
`backend/app/scripts/placeholders.py` into `frontend/public/seed/`. They are
abstract safety-sign boards in the correct signal colour for each category.

They are clearly marked `PLACEHOLDER ARTWORK` in the artwork itself, so a
placeholder can never be mistaken for a final asset during review. They do not
hotlink the legacy site's CDN, and the application does not depend on the legacy
site for any purpose.

Replacing them:

1. Upload real photography to Supabase Storage under
   `products/<category-slug>/<sku>-<n>.webp`.
2. Update `product_images.url` (or set `storage_path` and let the API mint
   signed URLs).
3. No code change and no migration.
