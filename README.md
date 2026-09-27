# Storefront

A production-grade ecommerce platform: Next.js storefront, FastAPI commerce API,
Supabase (PostgreSQL + Auth + Storage), Razorpay payments, and Redis-backed
background workers.

> **Status:** built in phases; see [`DEPLOYMENT_REPORT.md`](./DEPLOYMENT_REPORT.md)
> for what is verified, what is unverified, and the exact secrets still required.
> Nothing in this repository is claimed to be deployed unless the report says so
> with a verified URL.

---

## 1. Project overview

A complete storefront selling **premium audio and wearables** (headphones,
earbuds, speakers, smartwatches, accessories) with:

- Server-rendered catalogue with SEO metadata, structured data, sitemap and robots
- Server-authoritative cart, coupons, tax and shipping — the browser never sets a price
- Razorpay checkout with signature verification, idempotent webhooks and payment retries
- Transactional inventory reservation that cannot oversell under concurrency
- Customer account area and a staff admin dashboard, both server-authorised
- Provider-agnostic transactional email and a real background job worker

## 2. Architecture

Full detail, including the trust-boundary rules and the oversell-prevention SQL,
is in [`docs/ARCHITECTURE.md`](./docs/ARCHITECTURE.md).

```
Browser ──▶ Vercel (Next.js 16, App Router, RSC)
              │  HTTPS, CORS allow-list, Bearer token
              ▼
           Railway (FastAPI + uvicorn)  ──▶ Supabase (Postgres · Auth · Storage)
              │  ──▶ Razorpay (orders, webhooks)      Redis (rate limits, jobs)
              └──▶ separate Railway service: arq worker
```

Two deployable units, one owned datastore, and every secret that can be kept
out of the browser, is.

## 3. Tech stack

| Layer | Choice |
|---|---|
| Frontend | Next.js 16 (App Router), React 19, TypeScript, Tailwind CSS 4, shadcn/ui, Framer Motion, React Hook Form, Zod, TanStack Query |
| Backend | Python 3.13, FastAPI, Pydantic v2, SQLAlchemy 2 (async), Alembic, Uvicorn, `asyncpg` |
| Database | Supabase PostgreSQL 15+ |
| Auth | Supabase Auth (GoTrue), JWKS + HS256 verification in the API |
| Storage | Supabase Storage (private bucket, signed URLs) |
| Payments | Razorpay Orders + webhooks, hand-written async client |
| Jobs | arq on Redis, separate worker process |
| Email | Provider abstraction: console / Resend / AWS SES / SMTP |
| Tests | pytest, httpx, Vitest, Playwright |
| Deploy | Vercel (frontend), Railway (API + worker), Supabase (data) |

## 4. Folder structure

```
storefront/
├── frontend/            Next.js app (see frontend/README.md)
├── backend/             FastAPI service
│   ├── app/api/         routers, one per resource
│   ├── app/core/        config, logging, errors, security, middleware
│   ├── app/db/          engine, session, SQLAlchemy models
│   ├── app/schemas/     Pydantic contracts
│   ├── app/services/    domain logic — pricing, inventory, payments, email
│   ├── app/workers/     arq jobs and cron schedules
│   ├── alembic/         migrations
│   ├── scripts/seed.py  idempotent seed data
│   └── Dockerfile
├── database/sql/        Supabase-only SQL (RLS, storage, grants) — not Alembic's job
├── docs/                architecture and runbooks
└── scripts/             local bootstrap and verification helpers
```

## 5. Local setup

### Prerequisites

| Tool | Version used |
|---|---|
| Node.js | 22+ (24.13 verified) |
| Python | 3.12 or 3.13 (3.13 verified; 3.14 has no `psycopg` wheels) |
| PostgreSQL | 14+ (18.2 verified) — local only, Supabase in production |
| Redis | 6+ (optional locally; required for jobs) |

### Quickstart

```bash
git clone <your-repo> storefront
cd storefront
cp .env.example .env          # fill in values
npm run setup                 # installs frontend + backend + git hooks
```

<details>
<summary>Manual, per-service setup</summary>

```bash
# Backend
cd backend
py -3.13 -m venv .venv
.venv/Scripts/activate        # Windows: .venv\Scripts\activate
pip install -e ".[dev]"

# Frontend
cd ../frontend
npm install
cp .env.example .env.local
```
</details>

On Windows, `scripts/setup-backend.cmd` and `scripts/setup-frontend.cmd` do the
above with one command each.

## 6. Environment variables

Every variable is documented with purpose, format and safety notes in
[`.env.example`](./.env.example). The rules that matter most:

- **Never** commit `.env`. It is git-ignored and pre-commit blocks it.
- `SUPABASE_SERVICE_ROLE_KEY`, `RAZORPAY_KEY_SECRET`, `RAZORPAY_WEBHOOK_SECRET`
  and `JWT_SECRET` are **server only**. No `NEXT_PUBLIC_` prefix may ever be
  applied to them; the production config refuses to boot if one is present.
- `NEXT_PUBLIC_*` variables are inlined into the browser bundle at build time.
  Only the Supabase publishable key, the API URL, the Razorpay **key id** and
  the public site URL belong there.

Generating a signing secret:

```bash
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

## 7. Database setup

```bash
cd backend
python -m alembic upgrade head          # apply migrations
python -m scripts.seed                  # 24 products, variants, inventory, coupons
python -m scripts.seed --admin-email you@example.com --admin-password '…'
```

Migration workflow:

```bash
python -m alembic revision --autogenerate -m "add product tags"
python -m alembic upgrade head          # apply
python -m alembic downgrade -1          # roll back one revision
```

**Production rule:** schema changes go through Alembic only. No manual `ALTER`
against the production database. The rollback strategy is documented in
[`docs/DEPLOYMENT.md`](./docs/DEPLOYMENT.md).

Supabase-only SQL (Row Level Security, Storage buckets, grants) lives in
`database/sql/` and is applied once per project — see
[`docs/DEPLOYMENT.md`](./docs/DEPLOYMENT.md#5-supabase-only-sql).

## 8. Supabase setup

1. Create a project.
2. **Database** → copy the connection string. Use the **direct** host
   (`db.<ref>.supabase.co:5432`), *not* the transaction pooler — `asyncpg` uses
   server-side prepared statements, which the pooler in transaction mode rejects.
3. **Auth → URL Configuration**: Site URL = your frontend URL; add every redirect
   URL used by the email confirmation and password-reset links.
4. **Auth → Providers → Email**: enable email sign-in. Turn *Confirm email* on
   in production.
5. **API** → copy the project URL, the `anon`/publishable key and the
   `service_role` key. The service role key goes in the backend environment only.
6. Run `database/sql/001_extensions.sql`, `002_rls_policies.sql`,
   `003_storage.sql` in the SQL editor, then `npm run db:verify`
   (`backend/scripts/verify_schema.py`) to confirm the schema matches the models.

## 9. Razorpay setup

1. Create a test-mode account and note the **Key ID** and **Key Secret**.
2. Add a webhook: `POST https://<your-api-host>/api/v1/payments/webhook`
   with events `payment.captured`, `payment.failed`, `refund.processed`,
   `order.paid`, `order.failed`. Set a **webhook secret** and record it as
   `RAZORPAY_WEBHOOK_SECRET`.
3. Locally, forward webhooks with the Razorpay CLI:
   `razorpay webhook --url http://localhost:8000/api/v1/payments/webhook`
4. Set `RAZORPAY_MODE=test` until live keys are in place.

The API refuses to mark an order paid without a valid signature. With
`RAZORPAY_KEY_SECRET` unset, `/health/ready` reports `razorpay: degraded` and
payment routes return `503` rather than pretending to succeed.

## 10. Running the frontend

```bash
cd frontend
npm run dev            # http://localhost:3000
npm run build          # production build
npm run lint && npm run typecheck
npm run test           # vitest
npm run test:e2e       # playwright (needs a running stack)
```

## 11. Running the backend

```bash
cd backend
python -m uvicorn app.main:app --reload --port 8000
python -m app.workers                     # background job worker (separate process)
```

- API docs: `http://localhost:8000/api/docs`
- Liveness: `GET /health`
- Readiness: `GET /health/ready`

## 12. Running tests

```bash
cd backend
pytest tests/unit                        # no database required
TEST_DATABASE_URL=postgresql+asyncpg://... pytest tests/integration
pytest --cov=app --cov-report=term-missing

cd ../frontend
npm run test
npm run test:e2e
```

Integration tests skip themselves with a clear message when `TEST_DATABASE_URL`
is unset, so `pytest` never fails for the wrong reason.

## 13. Deployment

See [`docs/DEPLOYMENT.md`](./docs/DEPLOYMENT.md) for the full runbook, and
[`DEPLOYMENT_REPORT.md`](./DEPLOYMENT_REPORT.md) for what has actually been
performed. Summary:

| Target | What is deployed | Command |
|---|---|---|
| GitHub | whole monorepo | `git push origin main` |
| Vercel | `frontend/` | import repo, set root dir `frontend`, add `NEXT_PUBLIC_*` |
| Railway (api) | `backend/` | `railway up` / GitHub deploy, start `uvicorn app.main:app --host 0.0.0.0 --port $PORT` |
| Railway (worker) | `backend/` | second service, start `python -m app.workers` |
| Railway (migrate) | `backend/` | one-off: `python -m alembic upgrade head` |
| Supabase | — | run `database/sql/*.sql`, then migrate |

**Two Railway services are required.** The API alone is not a valid deployment;
see [`docs/DEPLOYMENT.md`](./docs/DEPLOYMENT.md#worker-service).

## 14. Production configuration checklist

- [ ] `APP_ENV=production` — the config validates this and refuses unsafe values
- [ ] `CORS_ORIGINS` lists the exact Vercel domain(s), never `*`
- [ ] `FRONTEND_URL` / `BACKEND_URL` are HTTPS and contain no `localhost`
- [ ] `JWT_SECRET` is 48+ random characters
- [ ] `SUPABASE_SERVICE_ROLE_KEY` and `RAZORPAY_KEY_SECRET` are set in Railway
- [ ] `RAZORPAY_WEBHOOK_SECRET` matches the dashboard
- [ ] Direct Postgres host, not the transaction pooler
- [ ] Redis attached; `worker` service deployed and reporting healthy
- [ ] Supabase RLS and Storage policies applied
- [ ] `DEBUG=false` so `/api/docs` is not public
- [ ] Email provider switched off `console`
- [ ] Admin role granted by `scripts/seed --admin-email`, never by a UI action

## 15. Admin setup

```bash
cd backend
python -m scripts.seed --admin-email you@example.com --admin-password 'strong-password'
```

The flag grants `profiles.role = 'ADMIN'` after the account exists. Admin
access is then enforced server-side on every `/api/v1/admin/*` route by the
`require_admin` dependency, which re-reads the role from the database on each
request — the frontend's copy of the role is irrelevant.

## 16. Background jobs

The worker runs as its own process (`python -m app.workers`) and consumes the
arq queue plus the cron schedules documented in
[`docs/ARCHITECTURE.md`](./docs/ARCHITECTURE.md#8-background-jobs). Jobs cover
transactional email, payment-intent expiry, abandoned-cart recovery, nightly
sales aggregation, inventory reconciliation, low-stock reporting and cleanup.

## 17. Troubleshooting

| Symptom | Cause and fix |
|---|---|
| Backend refuses to start in production | The config lists every unsafe value. Read the first lines of the traceback. |
| `500` on every request | Check `DATABASE_URL`. Verify direct host `:5432` and that the password has no URL-encoded specials. |
| `CORS` errors in the browser | `CORS_ORIGINS` must match the frontend origin exactly, including scheme and `www`. |
| `psycopg`/`asyncpg` install fails | Python 3.14 lacks wheels. Use 3.12 or 3.13. |
| Orders stuck in `PAYMENT_PENDING` | Reservation TTL. Run `expire_payment_intents`, or check the worker is running. |
| Webhook returns `400 signature` | `RAZORPAY_WEBHOOK_SECRET` differs from the dashboard value, or the body was altered in transit. |
| Emails not arriving | `EMAIL_PROVIDER=console` logs to stdout instead of sending. Set a real provider. |
| Admin pages 403 | The account's `profiles.role` is not `ADMIN`. Re-run the seed with `--admin-email`. |
| Migrations diverge on Supabase | Apply `database/sql/*.sql`, then `python -m alembic upgrade head`. Never hand-edit production tables. |

## 18. License

Private. All product copy, imagery and brand names in the seed data are
original placeholders intended to be replaced before going live.
