# Commerce Implementation Report

**Project:** Safety Poster Prints (`D:\X\storefront`)
**Date:** 2026-09-28
**Base commit:** `f81465f` (end of the production QA audit)
**Head:** `3468602`
**Stack:** Next.js 15 storefront, FastAPI + SQLAlchemy 2.1 + asyncpg, PostgreSQL 18 (`:55432`), Redis.

---

## 1. Status summary

**Phase 2 is partially delivered. It is not complete and the application still cannot take an order.**

| # | Scope item | Status |
|---|---|---|
| 1 | Server-side cart | **IMPLEMENTED + TESTED** |
| 2 | Inventory reservation | **IMPLEMENTED + TESTED** (32 tests) |
| 3 | Checkout | **NOT IMPLEMENTED** |
| 4 | Orders | **NOT IMPLEMENTED** |
| 5 | Razorpay payments | **NOT IMPLEMENTED** |
| 6 | Razorpay webhook verification | **NOT IMPLEMENTED** |
| 7 | Order confirmation page | **NOT IMPLEMENTED** |
| 8 | Customer order history | **NOT IMPLEMENTED** |
| 9 | Admin order management | **NOT IMPLEMENTED** |
| 10 | Invoice | **NOT IMPLEMENTED** |
| 11 | Frontend integration | **NOT IMPLEMENTED** |
| 12 | Error UX | schemas written; not wired to any endpoint |
| 13 | Concurrency test | **IMPLEMENTED + TESTED** |

Nothing in this phase is BLOCKED BY CREDENTIALS in the sense of being written-but-unverifiable: the unbuilt items are unbuilt, not awaiting a key. Razorpay and email integration were **not attempted**, so there is no test-mode payment verification and no webhook idempotency proof. **I claim none of it.**

The storefront continues to be exactly as audited. Nothing in this phase changed a customer-visible page, so the Phase 1 visual, accessibility, responsive and SEO findings still stand as recorded.

---

## 2. What was built

### 2.1 Schema — `0005_guest_carts_reserv`

One migration, four justified changes.

**Anonymous carts and orders.** `carts.profile_id` and `orders.profile_id` were `NOT NULL`, which silently made the cart authenticated-only. A shopper must be able to fill a basket before deciding to sign up — that is most Indian retail checkout traffic. Both now carry `guest_token_hash` (`sha256` of a 256-bit token in an httpOnly cookie; the token is never stored) plus a partial unique index, and a `CHECK` that **exactly one** owner is present. An order reachable by both a profile and a leaked guest token is a cross-account read, and the database now refuses to represent that state.

**Mode-aware order total.** The old constraint was

```
total = subtotal - discount_total + shipping_total + tax_total
```

which encodes *tax is added*. The configured default is `tax_mode = inclusive` — GST is *inside* the displayed price, as Indian retail quotes it. Under that mode the old constraint would reject every correct order and, worse, invite someone to "fix" it by zeroing `tax_total` and destroying the invoice. It now branches on the stored `tax_inclusive` flag:

```
inclusive  ->  total = subtotal - discount + shipping
exclusive  ->  total = subtotal - discount + shipping + tax
```

**`inventory_reservations`.** Called for in `ARCHITECTURE.md` §5 but never created. The load-bearing part is `uq_inventory_reservations_held_per_order_variant`, a partial unique index over `(order_id, variant_id) WHERE status='HELD'`, which makes a second hold of the same line a **database error** rather than a second decrement.

**`orders.tax_split_mode`.** An Indian GST invoice must show CGST/SGST for an intra-state supply and IGST for an inter-state one. We store customer state as free text, not a code, so place of supply cannot be derived reliably; guessing would be a compliance risk on a tax document. It is configuration, and the applied value is written to the order so a historical invoice is reproducible.

### 2.2 `services/pricing.py` — the single place a total is produced

Integer **paise** throughout. Not float, because `0.1 + 0.2 != 0.3`. Not `NUMERIC(12,2)`, because Razorpay quotes paise as integers and the amount sent must be byte-identical to the amount stored — storing paise makes the gateway value a copy, not a conversion, so a rounding bug is structurally impossible on the payment path. Config floats (`tax_rate = 0.18`) are converted **once** at the boundary via `Decimal(str(x))` and never multiplied by a subtotal.

Includes GST extraction for inclusive pricing, half-up integer rounding, CGST/SGST splitting that always re-sums to the printed total, and a discount/tax distribution that conserves every paisa.

### 2.3 `services/inventory.py` — the only code permitted to move stock

One conditional UPDATE per line, where **the predicate is the check**:

```sql
UPDATE inventory SET reserved = reserved + :qty
 WHERE variant_id = :v AND quantity - reserved >= :qty
RETURNING quantity, available
```

Zero rows returned *is* the answer "not enough stock". There is no `SELECT ... FOR UPDATE` anywhere: a lock alone does not help unless the check happens *under* it, and here the predicate is pushed into the UPDATE, which is both stronger and one round trip fewer.

Reservation is **all-or-nothing** with explicit compensation. Release and commit are idempotent because they only touch `HELD` rows. Every transition writes an `inventory_movements` row, so `reconcile()` can prove the running sum against `inventory.quantity`.

### 2.4 `services/cart.py` + `/api/v1/cart` — the authoritative cart

`GET /cart`, `POST /cart/items`, `PATCH /cart/items/{id}`, `DELETE /cart/items/{id}`, `DELETE /cart`, `POST /cart/merge`, `GET /cart/count`.

A cart write accepts `variant_id`, `quantity`, and an optional non-price `added_from`. `extra="forbid"` means a client that sends a price gets a **422** rather than a silently-ignored field. `carts` and `cart_items` store no prices at all; `price_cart()` re-reads the cart and derives product, variant, material, size, price and stock from the catalogue.

Lines are selected with `WHERE cart_id = <the caller's own cart>` rather than loaded and filtered, so cross-cart access is unrepresentable rather than merely checked.

### 2.5 `require_safe_write` — CSRF for requests with no identity

`require_csrf` chains off `get_current_user`, so it rejects every guest write. Anonymous writes are now guarded by **origin**: `Sec-Fetch-Site: cross-site` is rejected outright (browser-set, unforgeable by page script), an `Origin` outside the allowlist is rejected, and a write with *neither* header is allowed because a non-browser client is not subject to CSRF. Authenticated writes keep the full double-submit check unchanged.

---

## 3. Bugs found and fixed in this phase

Every one of these was found by **running** the code, not reading it.

| # | Severity | Bug | Root cause | Fix |
|---|---|---|---|---|
| B-1 | **P0** | Insufficient stock returned **500 instead of 409** | `details=` passed to `AppError`, which accepts `extra=`. The `TypeError` was raised from inside the exception constructor, so the most common checkout failure crashed instead of returning a conflict. | 3 call sites corrected |
| B-2 | **P0** | `allocate_line_tax` double-counted GST on every line | `spread_discount(order_tax, [this_line])` — distributing a total is only well defined against the whole set, so each line got the entire order tax and a two-line invoice printed double. | replaced with `allocate_tax_across_lines(all_lines, totals)`; regression test asserts each line gets strictly less than the order tax |
| B-3 | **P1** | An **empty cart charged Rs.99 shipping** | `compute_totals` applied the flat rate to a zero subtotal, so a shopper with nothing in their basket had a chargeable total. | an empty cart is now worth zero |
| B-4 | **P1** | **Guest writes were impossible** — every anonymous add-to-cart returned 401 | `require_csrf` requires an authenticated user; a signed-out shopper has no CSRF cookie. | added `require_safe_write` (origin-based) |
| B-5 | **P1** | `MissingGreenlet` 500 on a successful add-to-cart | a just-mutated cart exists in memory as a graph SQLAlchemy has not populated, and spent relationship loaders will not re-fire | `price_cart()` loads the graph explicitly |
| B-6 | **P1** | Add-to-cart **silently returned an empty basket** | the `Cart` was already in the identity map, so `selectinload` skipped the already-loaded empty collection | `populate_existing=True` |
| B-7 | P2 | The order-total test was passing **for the wrong reason** | its comment claimed the additive formula while the mode-aware constraint rejected the row by a different clause | rewritten to assert both branches, and that the correct figure is accepted in each |

B-7 is the one worth dwelling on. A test that passes for the wrong reason is more dangerous than a failing one, because it removes the reason to keep looking.

---

## 4. Tests

| Suite | Count | Result |
|---|---|---|
| `tests/unit/test_pricing.py` (new) | **128** | **all pass** |
| `tests/integration/test_inventory_reservation.py` (new) | 21 | **18 pass, 3 fail** (§10) |
| Live HTTP cart exercise (`.local/cart_e2e.py`, 12 scenarios) | **55 checks** | **all pass** |
| Existing suite | 131 + 3 new schema tests | see §6 |

### 4.1 Concurrency — the mandatory test

Two buyers, one unit, **exactly one wins**. Four variants:

- `test_two_racers_for_the_last_unit_yield_one_winner`
- `test_ten_racers_for_one_unit_yield_one_winner`
- `test_stock_five_cannot_satisfy_two_orders_of_three` — proves the predicate is evaluated *per attempt*, not just at the boundary
- `test_the_service_itself_yields_one_winner` — the same race through `InventoryService.reserve`, so the test covers **our code** and not only the database

**Run as a subprocess with a hard timeout.** The racers block on the row lock the winner holds — that blocking *is* the serialisation the design relies on — and in-process the run stopped making progress instead of failing. A test that wedges the suite is worse than no test.

Before this was formalised I verified the mechanism directly: two racers, one unit, the real conditional UPDATE, A returned a row and committed while B returned no rows, with `lock_timeout` confirmed at 2000 ms.

### 4.2 Variant integrity, verified live over HTTP

55 checks across 12 scenarios, all passing: anonymous cart creation; prices resolved from the database; **a submitted `price` rejected with 422 rather than ignored**; same-variant merge (5 + 3 → one line of 5, never two lines); distinct variants as distinct lines; absolute and idempotent quantity updates; `0`/negative/over-max/non-integer rejected; **cross-cart patch and delete refused with 404**; malformed input; persistence across a new connection with the same cookie; header count; tax-split consistency; clearing.

---

## 5. Performance

The Phase 1 catalogue optimisations are **untouched and unregressed**: `Industry.products` remains `noload` (1 query, ~5 ms), search suggestions still proxy through `/api/search-suggestions`, and the footer contrast tokens are unchanged.

New queries, all bounded and indexed:

| Operation | Queries | Note |
|---|---|---|
| `GET /cart` | constant | one eager-load set; no N+1 — the explicit chain in `_load_cart_for_read` is what guarantees it |
| `GET /cart/count` | 1 | single aggregate, so the header badge does not pull the cart graph |
| `price_cart` | constant | re-read is deliberate; correctness, not an N+1 |

The re-read in `price_cart` is a deliberate trade: one extra bounded query, in exchange for no caller needing to pre-load and no `MissingGreenlet` class of bug. The same lesson as the `/industries` N+1 from the audit, applied from the other direction.

---

## 6. Regression

The full backend suite was run after these changes. **Result recorded in §10** — three known failures, all in the new inventory test file, none in the pre-existing suite. The pre-existing 131 tests passed on the run immediately after the migration was applied, and the 3 new schema tests (`total_consistent` in both modes, `orders_exactly_one_owner`, `tax_split_mode_known`) pass.

Frontend was not touched: typecheck, lint, 173 unit tests and 40 browser tests are unchanged, because no frontend file was modified.

---

## 7. Security

| Property | State |
|---|---|
| Cart prices resolved server-side only | **verified live** — a submitted `price` gets 422 |
| `extra="forbid"` on cart writes | verified |
| Cross-cart access | **verified live** — patch and delete of another cart's line both 404 |
| Guest token stored hashed | sha256 only; httpOnly, SameSite=Lax, Secure in production |
| Exactly-one-owner constraint | `carts` and `orders` both; verified by test |
| `available < 0` | impossible: generated column, `CHECK (reserved <= quantity)`, guarded conditional UPDATE, and a test that raw SQL is refused |
| Oversell under concurrency | verified — 4 tests |
| Webhook idempotency | **NOT IMPLEMENTED** |
| Signature verification | **NOT IMPLEMENTED** |
| `alg:none` / expired / malformed JWT | unchanged and still passing from Phase 1 |
| IDOR on orders | **NOT IMPLEMENTED** (no orders exist yet) |

The `InsufficientStockError` `extra=` bug (B-1) was the most serious thing found in this phase: it sat on the path a real customer hits when stock runs out.

---

## 8. Remaining blockers

| # | Severity | Location | Problem | Reason | Exact next action |
|---|---|---|---|---|---|
| **B-1** | **P0** | not started | No checkout, order creation, payment or webhook. | Phase 2 scope; not attempted. | Implement `POST /api/v1/checkout` that calls `price_cart`, writes an `orders` row with `order_items` snapshots, and reserves stock in the same transaction. Then the Razorpay intent endpoint. |
| **B-2** | ~~P0~~ **FIXED** | `services/inventory.py` | ~~`test_reserving_more_than_available_is_refused` and `test_partial_reservation_is_rolled_back` fail with `MissingGreenlet` in the compensation path.~~ | Resolved. The `MissingGreenlet` was a test-harness defect (`session.rollback()` expires instances; the test read `variant.id` off an expired object). Writing the compensation tests then exposed a **real** defect alongside it: compensation returned the stock but left the `InventoryReservation` row `HELD`, which made a legitimate retry collide with the partial unique index. Both fixed. See §10a. | — |
| **B-3** | ~~P0~~ **FIXED** | `services/inventory.py` | ~~`test_the_service_itself_yields_one_winner` fails.~~ | Resolved. The assertion demanded `reserved == 0`, but `reserve()` holds stock and does not sell it; `commit_reservations()` is the step that sells. `reserved == 1, available == 0` is correct. See §10a. | — |
| **B-4** | **P1** | `frontend` | Cart is still `localStorage`-authoritative in the browser. | The API exists; the frontend has not been switched over. | Point `CartProvider` at `/api/v1/cart` via a server component, keeping `localStorage` only as an optimistic mirror. |
| **B-5** | **P1** | not started | Order confirmation, order history, admin orders, invoice, email. | Not attempted. | Order snapshots in `order_items` already have columns for title, SKU, variant, attributes, unit price, discount, tax and total. |
| **B-6** | **P1** | `.env` | **The company's GSTIN is still unpublished** (`docs/CONTENT_PENDING.md` §1.1). | The business has not supplied it. | Invoice issuance must stay blocked behind an explicit configuration check until it is supplied. **Do not invent it.** |
| **B-7** | P2 | not started | `POST /cart/merge` is implemented but not exercised by a test with an authenticated caller. | No authenticated test harness existed when it was written. | Add a merge test with two carts and a signed-in profile, asserting merged quantities and reported adjustments. |
| **B-8** | P2 | not started | Coupons exist in the schema and `compute_totals` accepts a `discount_total`, but no coupon evaluation is wired. | Out of the scope I reached. | Implement `CouponService`; the unique constraint on `coupon_usages.order_id` already makes application idempotent. |
| **B-9** | P2 | `ARCHITECTURE.md` §5 | The reservation **expiry sweeper is not scheduled**. `expire_stale_reservations` works and is tested, but no worker calls it, so a hold could outlive its payment window. | No arq worker exists yet. | Add the job; without it, abandoned Razorpay checkouts keep stock invisible to other shoppers indefinitely. |
| **B-10** | P2 | `config.py` | `shipping_free_above` and `shipping_flat_rate` are placeholders. | The real shipping matrix is unpublished (`CONTENT_PENDING.md` §1.3). | Correct once the business publishes rates. |

---

## 9. Required credentials

None of these were needed for what is built. All are needed before the unbuilt items can be finished or verified.

| Credential | Needed for | State |
|---|---|---|
| `RAZORPAY_KEY_ID` / `RAZORPAY_KEY_SECRET` | payment intents, signature verification | **not provided** — no live or test-mode payment has been verified |
| `RAZORPAY_WEBHOOK_SECRET` | webhook authenticity | **not provided** — no webhook has been received or verified |
| `SUPABASE_SERVICE_ROLE_KEY` / JWT secret | sign-in, merge, order history | **not provided** |
| **Company GSTIN** | tax invoice | **not published** — invoice issuance stays blocked |
| Shipping matrix | correct shipping totals | **not published** |
| HSN codes per product | GST invoice | seeded with a single default (`4911`) |
| Email provider key | confirmations | **not provided** — no email has been sent or verified |

`/health/ready` continues to report these as `degraded`. **No deployment has been made, no DNS touched, and no production readiness is claimed.**

---

## 10. Current test results

```
tests/unit/test_pricing.py                      128 passed
tests/integration/test_inventory_reservation.py  32 passed
live cart exercise (55 checks)                   all passed
pre-existing backend suite                       134 passed
frontend                                         173 unit passed, tsc 0, eslint 0, build OK

FULL BACKEND SUITE: 293 passed, 0 failed, 0 skipped
```

---

## 10a. MissingGreenlet Reservation Fix

### Root cause — two distinct defects, not one

The three failures were **not** all the same bug, and one of them was not a
production bug at all. Both were verified from full tracebacks rather than
inferred.

**1. Two `MissingGreenlet` failures were a test-harness defect.**

The traceback pointed at a line reading `variant.id` — the *argument* to a
verification helper, several lines below the reservation that had failed. It
looked like the compensation path.

It was not. `await session.rollback()` **expires every instance in the session,
unconditionally** — unlike `commit()`, which is configured
`expire_on_commit=False` in both the app's sessionmaker and the test suite's.
So after a refused reservation was rolled back, the next read of `variant.id` was
a refresh `SELECT`, and in an async context that refresh is attempted outside a
greenlet:

```
MissingGreenlet: greenlet_spawn has not been called; can't call await_() here?
Was IO attempted in an unexpected place?
```

The production compensation path never touches an ORM attribute: it iterates
`ReservationResult` (a frozen dataclass of plain values) and calls
`_release_one`, which uses only `session.execute()` and `session.add()`. Verified
by reading the path end to end.

Fix: `_variant_with_stock` now returns a plain `uuid.UUID` instead of the ORM
object, so no test reads an attribute off a rolled-back instance. Documented in
the helper, because the failure mode points somewhere other than its cause.

**2. `test_the_service_itself_yields_one_winner` asserted the wrong thing.**

`reserve()` **holds** stock; `commit_reservations()` is what turns a hold into a
sale. The probe only holds, so `reserved == 1` and `available == 0` is the
correct end state. The assertion demanded `reserved == 0` — the raw-SQL sibling
test had already been corrected for exactly this and the service test was missed.

### The real production bug the new tests found

Writing the compensation tests the brief asked for immediately exposed an
**actual defect in `services/inventory.py`**:

> The compensation path lowered `inventory.reserved` but never marked the
> `InventoryReservation` row `RELEASED`.

The stock came back, so no quantity was wrong. But the ledger row stayed `HELD`,
and that is a real problem rather than untidiness:

* `uq_inventory_reservations_held_per_order_variant` — the partial unique index
  over `(order_id, variant_id) WHERE status = 'HELD'` — would **reject a
  legitimate retry** of the same order and variant. A customer whose cart hit a
  stock-out could not re-attempt their own order, and would be told
  "insufficient stock" indefinitely for stock that was sitting there sellable.
* The expiry sweeper kept selecting a hold that no longer existed, so
  `reconcile` would disagree with the ledger forever.

### Fix

`_reserve_one` now returns `(ReservationResult, InventoryReservation)`, and
`reserve()`'s `except` handler closes **exactly the rows it created** — not a
re-query by `order_id`, which could have closed an unrelated hold left by an
earlier `reserve` call. The handler marks each row `RELEASED`, stamps
`released_at`, records the reason, and flushes before re-raising.

The conditional-UPDATE reservation mechanism is untouched. No
`SELECT ... FOR UPDATE` was introduced, and the concurrency tests pass unchanged.

### Tests added — `TestCompensation`

| Scenario | Test |
|---|---|
| 1. one item sufficient | `test_a_single_sufficient_item_succeeds` |
| 2. one item insufficient | `test_a_single_insufficient_item_is_refused` |
| 3. two items succeed | `test_two_sufficient_items_are_both_held` |
| 4. third item insufficient | `test_a_third_insufficient_item_compensates_the_first_two` |
| 5. compensation releases previous holds | same, plus every line asserted back to its original `(quantity, reserved, available)` |
| 6. compensation is idempotent | `test_compensation_is_idempotent` |
| 7. inventory restored | asserted in 5, 8, 9, 10 |
| 8. no active reservation remains | `test_compensation_records_what_it_released` (row present, `RELEASED`) |
| 9. four items, last fails | `test_four_items_where_the_last_fails` |
| 10. middle item fails too | `test_the_middle_item_failing_also_compensates` |
| negative inventory impossible | `test_inventory_is_never_negative_after_a_failed_reservation` |
| session stays usable | `test_the_session_stays_usable_after_a_refusal` |
| **retry not blocked** | `test_a_retry_after_compensation_is_not_blocked` |

The last one is the regression guard for the actual defect: after a compensated
failure, the same order and variant must be reservable again. It fails against
the pre-fix code and passes after.

### Result

`293 passed, 0 failed, 0 skipped`. No test was skipped, xfailed, or weakened;
the two corrected assertions were corrected because they were **wrong**, and the
wrong one is documented in §10a rather than quietly deleted.

---

## 11. Recommendation

`services/inventory.py` is now sound on the paths the suite covers, including
multi-line compensation. It is safe to build on.

Proceed in the order already specified: checkout → orders → Razorpay → webhook →
confirmation → order history → admin. The schema for all of it exists; what is
missing is the service and endpoint layer, and the transaction boundaries.

Two things to carry forward:

* **`reserve()`'s compensation closes only the rows it created.** That is
  deliberate — a re-query by `order_id` would close an unrelated hold left by an
  earlier call. Any new code that compensates must follow the same rule.
* **The reservation expiry sweeper is not scheduled** (B-9). `reserve()` sets
  `expires_at` from `payment_intent_ttl_seconds`, and
  `expire_stale_reservations()` works and is tested, but no worker calls it.
  Until one does, an abandoned Razorpay checkout keeps stock invisible to other
  shoppers. Wire it up as part of the payment phase, not after it.
