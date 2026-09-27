# Architecture

## 1. System context

```
                        ┌──────────────────────────────┐
   Browser  ──────────▶ │  Vercel  ·  Next.js 16       │
   (mobile first)       │  App Router, RSC, Edge/CDN   │
                        └───────────────┬──────────────┘
                                        │  HTTPS  ·  CORS allow-list
                                        │  Bearer <supabase access token>
                                        ▼
                        ┌──────────────────────────────┐
                        │  Railway  ·  FastAPI         │
                        │  uvicorn 0.0.0.0:$PORT       │
                        │  ┌────────────────────────┐  │
                        │  │ api/v1 (routers)       │  │
                        │  │ services (domain)      │  │
                        │  │ jobs (arq, separate)   │  │
                        │  └────────────────────────┘  │
                        └───┬───────────┬───────────┬──┘
                            │           │           │
              ┌─────────────▼──┐  ┌─────▼──────┐  ┌─▼──────────────┐
              │ Supabase      │  │  Razorpay  │  │ Email provider │
              │ PostgreSQL    │  │  Orders +  │  │ Resend / SES / │
              │ Auth (GoTrue) │  │  Webhooks  │  │ SMTP / console │
              │ Storage       │  └────────────┘  └────────────────┘
              │ Redis (plugin)│
              └────────────────┘
```

Two deployable compute units (frontend, API), one worker process group, and
three managed services. The only stateful component we own is Postgres.

## 2. Trust boundaries

This is the part of the system that must be right, so it is stated explicitly.

| Boundary | Rule |
|---|---|
| Browser → API | Every field is untrusted. Prices, discounts, roles, stock and totals are **re-read from the database**. |
| Browser → Auth | Role claims in a JWT are a hint only. Admin is granted when `profiles.role = 'ADMIN'` **and** the JWT signature verified against Supabase. |
| Razorpay → API | Webhook bodies are only trusted after an HMAC-SHA256 signature check against `RAZORPAY_WEBHOOK_SECRET`, compared with `hmac.compare_digest`. |
| Admin → API | Guarded by `require_admin` dependency on **every** admin route. There is no "the frontend hides the link" defence. |
| Service → DB | The `service_role` key is read only inside the API process. It is never prefixed `NEXT_PUBLIC_`, never returned by an endpoint, and never logged. |

### Order of operations for money

The browser can only ever tell the server *what* it wants, never *what it costs*:

```
POST /api/v1/cart/items { variant_id, quantity }
      └─▶ server loads variant, reads price_*, checks available stock

POST /api/v1/checkout { address_id, shipping_method, coupon_code }
      └─▶ server recomputes: unit prices → line totals → coupon → shipping
                             → tax → grand total   (all in one transaction)

POST /api/v1/payments/create { checkout_id }
      └─▶ server re-validates stock, reserves inventory, calls Razorpay

POST /api/v1/payments/verify { razorpay_order_id, razorpay_payment_id, signature }
      └─▶ server recomputes expected HMAC, then transitions order → PAID
```

Because the total that the customer signed with Razorpay is produced by the
server and re-verified against a server-side recomputation, a tampered client
total is not merely ignored — the signature will not match and the order stays
unpaid.

## 3. Repository layout

```
storefront/
├── frontend/                 Next.js 16 App Router (TypeScript, RSC)
│   ├── src/app/              routes, layouts, server components
│   ├── src/components/       design-system + feature components
│   ├── src/lib/              api client, auth, cart state, formatting
│   └── vercel.json           deployment + security header config
├── backend/                  FastAPI service
│   ├── app/
│   │   ├── api/              routers, one module per resource
│   │   ├── core/             config, logging, errors, security, middleware
│   │   ├── db/               engine, session, models
│   │   ├── schemas/          Pydantic request/response contracts
│   │   ├── services/         domain logic (pricing, inventory, payments, …)
│   │   └── workers/          arq job functions + schedules
│   ├── alembic/versions/     ordered, reversible migrations
│   ├── scripts/seed.py       idempotent realistic seed data
│   ├── Dockerfile            production image
│   └── railway.json
├── database/                 Supabase-managed SQL Alembic does NOT own
│   └── sql/                  RLS policies, storage buckets, realtime, grants
├── docs/                     architecture, runbooks, ADRs
└── scripts/                  dev bootstrap, verification helpers
```

### Why the recommended structure was kept, with one clarification

The recommended `frontend/ backend/ database/ docs/ scripts/` split is used
unchanged, because a monorepo with a single deployable per folder is the right
shape for a Vercel + Railway split.

The clarification: **`database/` is not a second copy of the schema.** Duplicating
DDL in two places guarantees drift. Instead:

* **Alembic owns the schema.** It is the only thing allowed to `CREATE/ALTER`
  tables, enums and indexes, for local and production alike.
* **`database/sql/` owns what Alembic must not** — Supabase-specific concerns
  that are declarative platform configuration rather than schema history:
  Row Level Security policies, Storage bucket definitions and policies,
  `realtime` publication membership, and role grants. These are applied
  idempotently by `scripts/db-apply-supabase.mjs` / the documented SQL editor
  paste, and are intentionally *not* part of the migration chain.

`database/sql/002_rls_policies.sql` is the reason: RLS is the defence in depth
behind a service-role API. The API bypasses it (it needs to read other users'
orders as staff), so RLS exists specifically to contain a leaked `anon` key.

## 4. Data model

Full column-level detail lives in `database/sql/000_schema_reference.sql`,
which is generated from the live database and checked for drift.

```
auth.users (Supabase managed)
      │ 1:1  trigger on insert
      ▼
profiles ──────────── addresses
      │ 1:N             user_id ──▶ auth.users
      │
      ├──▶ orders ──▶ order_items ──▶ product_variants ──▶ products ──▶ categories
      │       │              (price *captured at purchase time*)   │
      │       ├──▶ payments                                    └──▶ product_images
      │       └──▶ shipments
      │
      ├──▶ cart_items ──▶ cart
      ├──▶ wishlist_items ──▶ wishlist
      ├──▶ reviews ──▶ products        (verified_purchase from orders)
      └──▶ audit_logs
```

Notable modelling decisions:

* **`order_items` snapshots `unit_price`, `title` and `sku`.** A later catalogue
  price change must never retroactively alter what a customer was charged, and
  a deleted product must not make a past order unreadable.
* **`inventory` is one row per variant**, with `quantity`, `reserved` and
  `low_stock_threshold`. `available = quantity - reserved` is computed in SQL
  (a generated column) rather than trusted from the application.
* **`products.price_min` is a generated column** derived from live variant
  prices, so a listing can render "from ₹X" without an N+1 aggregate.
* **No stored money totals on `carts`.** The cart is recomputed on read; a
  cached total can only ever be stale or tampered.

## 5. Inventory and oversell control

Oversell is prevented with a single atomic statement rather than
read-then-write, so two concurrent checkouts for the last unit cannot both win.

```sql
-- reserve
UPDATE inventory
   SET reserved = reserved + :qty
 WHERE product_variant_id = :variant
   AND quantity - reserved >= :qty
RETURNING quantity, reserved;
```

Zero rows returned ⇒ not enough stock ⇒ the caller raises
`insufficient_stock`. The `RETURNING` clause means no lock is held between the
check and the write, and PostgreSQL's row lock serialises competing updates.

Lifecycle:

| Event | Effect |
|---|---|
| Cart item added | availability *checked*, nothing reserved (stock is not held by carts) |
| `payments/create` | `reserved += qty` inside the checkout transaction |
| Payment verified / webhook `captured` | `quantity -= qty`, `reserved -= qty` |
| Payment `failed` / `cancelled`, or intent expiry | `reserved -= qty` (released) |
| Order cancelled | `quantity += qty` for every line |
| Order refunded | stock is **not** automatically restocked; admin chooses, so a returned item is not resold by accident |

An `inventory_reservations` ledger (Phase 7) records each transition with a
reason so a leaked reservation is always traceable and reconcilable.

## 6. Authentication and authorization

Supabase GoTrue issues the access token; the API only *verifies* it.

```
supabase.auth.signInWithPassword()      → session.access_token
Authorization: Bearer <access_token>
      └─▶ verify signature (HS256 secret, or ES256/RS256 via Supabase JWKS)
      └─▶ check exp / issuer / audience
      └─▶ SELECT role FROM profiles WHERE id = sub
```

* `SUPABASE_JWT_SECRET` is only required for legacy HS256 projects. New Supabase
  projects use asymmetric keys, so the verifier fetches and caches
  `/.well-known/jwks.json` and validates with the public key. Both paths are
  implemented and the JWKS response is cached in Redis with a TTL, so a cold
  start does not hit the auth server on every request.
* **No session cookie is minted by the API.** The frontend holds the Supabase
  session and sends the bearer token. This removes an entire class of CSRF and
  cookie-theft risk from the API surface. The API is therefore not
  cookie-authenticated, and mutating routes are protected by CORS plus bearer
  tokens rather than `SameSite` alone.
* `JWT_SECRET` is still required, and is used to sign short-lived internal
  tokens for worker hand-off and privileged back-office callbacks — a separate
  key space from Supabase's, so compromising one does not compromise the other.

Role checks are expressed as FastAPI dependencies, which makes them impossible to
forget on a route:

```python
router = APIRouter(prefix="/admin", dependencies=[Depends(require_admin)])
```

## 7. Payments

Razorpay is integrated through a small hand-written async client
(`app/services/razorpay/client.py`) rather than the vendor's synchronous SDK.
The SDK is `requests`-based and blocking, which would force threadpool hops
inside an async handler. The client covers exactly what we need — create order,
fetch order, fetch payment, refund — over `httpx`, and keeps signature
verification in our own testable code.

State machine, with every transition guarded server-side:

```
checkout draft ──POST /payments/create──▶ PAYMENT_PENDING ──verify ok──▶ PAID
                                              │                             │
                                              └──verify fail/TTL──▶ PENDING │ PROCESSING
                                                                        │  SHIPPED
                                                                        │    DELIVERED
                                                     refund ──▶ REFUNDED ┘
```

* Verification recomputes `HMAC_SHA256(order_id + "|" + payment_id, key_secret)`
  and compares with `hmac.compare_digest`. Order amount is re-read from the
  order row and compared to the Razorpay order amount before capture.
* `payments` carries a unique constraint on `razorpay_payment_id` and the
  confirm-order transaction takes `SELECT … FOR UPDATE` on the order row, so a
  replayed verify or webhook cannot double-apply.
* The webhook is the source of truth for settlement. The client-side verify
  call is an optimisation that gets the customer to the confirmation page fast.
  Both paths funnel into one idempotent `settle_order()` service function.

## 8. Background jobs

Anything that must not add latency to a customer request, or that must run on a
schedule, is an **arq** job on Redis. The API and the worker are **separate
Railway services** from the same image, selected by start command:

| Service | Start command | Purpose |
|---|---|---|
| `api` | `uvicorn app.main:app --host 0.0.0.0 --port $PORT` | HTTP only |
| `worker` | `python -m app.workers` | Jobs + cron |

| Job | Trigger | What it does |
|---|---|---|
| `send_email` | enqueued | provider-agnostic transactional email |
| `expire_payment_intents` | cron, hourly | release reservations for abandoned checkouts |
| `mark_abandoned_carts` | cron | flag carts for recovery, enqueue nudge email |
| `recover_abandoned_carts` | cron | email customers who left items behind |
| `aggregate_sales_daily` | cron, nightly | roll orders into `analytics_daily` for the admin charts |
| `reconcile_inventory` | cron, nightly | detect drift between ledger and `inventory` |
| `low_stock_report` | cron, daily | notify staff about variants below threshold |
| `newsletter_digest` | cron, weekly | campaign summary |
| `clean_expired_data` | cron, daily | purge abandoned drafts, stale idempotency keys, old OTPs |

Enqueueing happens from the API; consuming happens only in the worker. If the
worker is down, orders still complete — the API writes an outbox row in the same
transaction and the worker drains it. That is the difference between "jobs are
best effort" and "jobs are guaranteed".

## 9. Caching

* **Redis** for rate limit counters, JWKS cache, and product catalogue snapshots.
* **HTTP caching** via `Cache-Control`/`ETag` on public catalogue reads, plus
  `stale-while-revalidate` so a cold CDN never blocks a shopper.
* **Next.js** `revalidateTag`/`revalidatePath` from admin mutations to purge the
  storefront instantly after a product or price change.
* No cache is ever used for cart, checkout, orders or payments. Those are
  per-user, money-bearing and must always be read through.

## 10. Observability

* JSON logs with `request_id` on every line, echoed to the client as
  `X-Request-ID`.
* `GET /health` (liveness) and `GET /health/ready` (per-dependency readiness,
  503 when Postgres is down) so Railway can drain a broken instance.
* `audit_logs` records every privileged mutation — who, what, when, before and
  after — for order status changes, refunds, product edits, role changes and
  coupon edits. Customer-visible state is never changed without a row here.
* Payment gateway errors are logged with full context (order id, razorpay ids,
  error code) but never with secrets.

## 11. Testing strategy

| Layer | Location | Needs a database? |
|---|---|---|
| Unit — pricing, coupons, tax, signature verification | `backend/tests/unit` | no |
| Integration — repositories, services, transactions | `backend/tests/integration` | yes (skipped if absent) |
| API — routes, auth, RBAC, error envelope | `backend/tests/api` | yes |
| Frontend component / unit | `frontend/src/**/*.test.tsx` | no |
| E2E — Playwright against a running stack | `frontend/e2e` | yes |

Oversell is tested directly: two concurrent reservations for the last unit must
result in exactly one success. That is the test that proves the inventory design.

## 12. Decisions deliberately *not* taken

* **No micro-frontends, no monorepo tooling (Nx/Turbo).** Two deployables do not
  justify the extra moving parts.
* **No Redis for carts.** The cart must be transactional with inventory and the
  order, which Postgres already gives us. A second datastore would add a
  consistency problem to buy a cache we would have to invalidate anyway.
* **No ORM-level multi-tenancy.** One storefront, one catalogue.
* **No `Decimal` in the database.** Money is `BIGINT` minor units end to end;
  `Decimal` appears only in formatting for display.
