# Deployment

How to deploy this project to Vercel (storefront) and Railway (API).

**Nothing in this document has been deployed.** No DNS, no production domain, no
gateway credentials. Every claim below is a configuration instruction or a
locally measured result. Where a platform setting is required from you, it is
called out explicitly.

---

## 1. Repository structure

```
storefront/
├── backend/              FastAPI service  -> Railway
│   ├── app/              application package (app.main:app)
│   ├── alembic/          migrations (7 revisions)
│   ├── alembic.ini
│   ├── pyproject.toml    dependencies live here; there is no requirements.txt
│   ├── Dockerfile
│   ├── railway.json
│   ├── .dockerignore
│   └── .env.example
├── frontend/             Next.js 16 storefront -> Vercel
│   ├── src/app/          App Router pages and the /api route handler
│   ├── .env.example
│   └── .env.local        git-ignored, local only
├── database/             schema reference SQL
├── docs/
└── .env.example          shared/root template
```

**The backend and frontend deploy from different subdirectories.** This is the
single most important structural fact, and misreading it is what produces
"Dockerfile failed validation".

---

## 2. Vercel configuration

| Setting | Value | Why |
|---|---|---|
| Root Directory | `frontend` | the app is not at the repo root |
| Framework Preset | Next.js (auto-detected) | |
| Build Command | `npm run build` | default; no override needed |
| Install Command | `npm install` | default |
| Node version | 20 or newer | Next.js 16 requirement |

**No `vercel.json` is needed.** Vercel ships a *verified adapter* for Next.js
that is built on the public Deployment Adapter API, so `next build` output is
consumed directly. Adding a `vercel.json` would only risk overriding working
defaults.

### Build-time requirements

The build **genuinely needs a reachable API**, not just the variables. From
`next build`:

| Route | Rendering | Why it needs the API at build |
|---|---|---|
| `/` | static, `revalidate: 30s` | prerenders the catalogue |
| `/blog/[slug]` | SSG | `generateStaticParams` needs the slugs |
| `/policies/[slug]` | SSG | `generateStaticParams` needs the slugs |
| `/shop`, `/products/[slug]`, `/category/*`, `/search`, `/blog`, `/industries/*`, `/5s`, `/msds`, `/bulk-order`, `/sitemap.xml` | dynamic | API on every request |

So deploy in this order: **API first, then storefront.** The storefront's build
must be able to reach the API, and it must stay reachable for the dynamic routes
afterwards.

---

## 3. Vercel environment variables

Settings → Environment Variables. Add to **both** Production and Preview.

| Variable | Required | Example | Notes |
|---|---|---|---|
| `NEXT_PUBLIC_API_URL` | **yes, at build time** | `https://your-api.up.railway.app` | no trailing slash; stripped on read |
| `NEXT_PUBLIC_SITE_URL` | **yes, at build time** | `https://your-app.vercel.app` | absolute; used for canonical, OG, sitemap, robots |
| `NEXT_PUBLIC_SITE_NAME` | no | `Safety Poster Prints` | |
| `NEXT_PUBLIC_SUPABASE_URL` | no | | signed-out account pages until set |
| `NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY` | no | | publishable key only |
| `NEXT_PUBLIC_RAZORPAY_KEY_ID` | no | | unused until payments exist |

**`NEXT_PUBLIC_*` is inlined at build time.** Setting a variable after a build
changes nothing until you redeploy. Add them before the first deploy.

### What must never be set on Vercel

`NEXT_PUBLIC_` values are shipped to the browser and are readable in page
source. Never put any of these in the Vercel project:

```
SUPABASE_SERVICE_ROLE_KEY   bypasses all row-level security
SUPABASE_JWT_SECRET         forges any user's access token
RAZORPAY_KEY_SECRET         authorises charges and refunds
RAZORPAY_WEBHOOK_SECRET     forges webhook deliveries
DATABASE_URL                the database password
JWT_SECRET                  signs internal tokens
```

The frontend never reads any of them. The only browser `fetch` in the codebase
is `SearchBox` → `/api/search-suggestions`, a same-origin Next route handler that
calls the API server-side.

### Failure modes

| Message | Cause |
|---|---|
| `Missing required environment variable NEXT_PUBLIC_SITE_URL` | variable not set on the deployment's environment |
| `Error occurred prerendering page "/"` | `NEXT_PUBLIC_API_URL` set but the API is unreachable from the build |
| `Failed to collect configuration for /blog` | `NEXT_PUBLIC_SITE_URL` missing |
| `Failed to collect page data for /products/...` | API reachable but returning an error |

---

## 4. Railway configuration

| Setting | Value | Why |
|---|---|---|
| Root Directory | `backend` | **the cause of the reported failure** |
| Builder | Dockerfile | `backend/railway.json` declares this |
| Dockerfile path | `Dockerfile` | relative to the root directory |
| Healthcheck path | `/health` | declared in `railway.json` |

### "The Dockerfile failed validation"

**Root cause: there was no Dockerfile.** The repository contained no
`Dockerfile`, no `railway.json` and no `Procfile` at any point before this
change, so a Dockerfile build had nothing to validate.

`backend/railway.json` now makes the build explicit:

```json
{
  "build": { "builder": "DOCKERFILE", "dockerfilePath": "Dockerfile" },
  "deploy": {
    "startCommand": "uvicorn app.main:app --host 0.0.0.0 --port $PORT",
    "healthcheckPath": "/health"
  }
}
```

Because the root directory is `backend`, the `COPY` paths in the Dockerfile are
backend-relative. If you instead set the root directory to the repository root,
every `COPY` in the Dockerfile would have to become `backend/...` — the two
cannot be mixed.

### Locally

```bash
cd backend
docker build -t storefront-api .
docker run --rm -p 8080:8080 \
  -e DATABASE_URL="postgresql+asyncpg://user:pass@host:5432/db" \
  -e APP_ENV=production \
  -e JWT_SECRET="<32+ random characters>" \
  -e CORS_ORIGINS="http://localhost:3000" \
  -e FRONTEND_URL="http://localhost:3000" \
  -e BACKEND_URL="http://localhost:8080" \
  -e SUPABASE_SERVICE_ROLE_KEY="<key>" \
  storefront-api
curl -i http://localhost:8080/health     # -> 200 {"status":"ok","version":"1.0.0"}
```

**The image is not verified.** Docker was not installed on the machine this was
authored on, so the Dockerfile has been statically validated only: every `COPY`
source confirmed to exist relative to the `backend/` context, the Python version
checked against the `requires-python` pin, and the start command and health
endpoint confirmed against a locally running server. Treat the first Railway
build as the real test.

---

## 5. Railway environment variables

Service → Variables. `backend/.env.example` is the annotated template.

### Required to start

| Variable | Notes |
|---|---|
| `DATABASE_URL` | asyncpg URL. The Railway Postgres plugin injects this automatically. |
| `JWT_SECRET` | ≥32 characters, not the placeholder, or the app refuses to start in production. |
| `CORS_ORIGINS` | comma-separated. **No wildcards** — a validator rejects `*`. Set this to the Vercel domain. |
| `FRONTEND_URL` | used for CORS and self-referential links |
| `BACKEND_URL` | must not be localhost in production |

Startup is **lazy**: the app binds its port without touching PostgreSQL or Redis,
so a database that is briefly unavailable causes failed requests rather than a
crash loop.

### Required in production for auth

| Variable | Notes |
|---|---|
| `SUPABASE_SERVICE_ROLE_KEY` | `APP_ENV=production` refuses to start without it |
| `SUPABASE_URL` | |
| `SUPABASE_JWT_SECRET` | only legacy HS256 projects |

The catalogue does not need Supabase. A deployment without it serves browsing
and the public API and shows signed-out account pages — but it will not start
with `APP_ENV=production`, which is deliberate: an account system that silently
accepts unverified tokens is worse than one that is visibly unavailable.

### Required only for payments — not required yet

`PAYMENTS_ENABLED`, `RAZORPAY_KEY_ID`, `RAZORPAY_KEY_SECRET`,
`RAZORPAY_WEBHOOK_SECRET`.

The checkout → order → payment pipeline is not built, so there is no payment
route to misconfigure. `PAYMENTS_ENABLED` defaults to `false` and the three
credentials are then not required. **Setting `PAYMENTS_ENABLED=true` makes all
three mandatory again** — the check is gated on the feature, not removed:

```
PAYMENTS_ENABLED is set, so RAZORPAY_KEY_ID and RAZORPAY_KEY_SECRET are required
```

Verified locally in both directions.

### Required only for email — not required yet

`EMAIL_PROVIDER` defaults to `console`, which logs the message and needs no
credentials. `RESEND_API_KEY` or the `SMTP_*` group is needed only when you
switch to a real provider. No order-email path exists yet.

### Optional

`REDIS_URL` (rate limiting, caching, arq queue — features degrade without it),
`DATABASE_READ_URL`, `DB_POOL_*`, `TAX_*`, `SHIPPING_*`, `CURRENCY_*`,
`WORKER_CONCURRENCY`, `JOB_*`.

---

## 6. Database configuration

One database, owned by the backend. The frontend has no database configuration
and must never receive `DATABASE_URL`.

1. Railway project → **Add plugin → PostgreSQL**. It creates the database and
   injects `DATABASE_URL` as a service variable.
2. `DATABASE_READ_URL` is optional; it falls back to `DATABASE_URL`.

`alembic.ini` contains a placeholder `sqlalchemy.url` that is never used —
`alembic/env.py` reads `get_settings().effective_database_url`, i.e.
`DATABASE_URL`. So no URL needs editing into `alembic.ini`.

Pool size defaults are deliberately small (5 + 5 overflow). A large pool behind
Railway's connection proxying is a common way to exhaust Postgres connections and
produce 503s that look like application errors.

---

## 7. Migrations

**Migrations are not run on container start.** With more than one replica, every
replica would migrate on boot and one would fail on a lock. The image ships
`alembic/` and `alembic.ini` so migrations can be run as a deliberate,
one-off step.

**Before the first deploy, and after every schema change:**

```bash
railway run alembic upgrade head
railway run python -m scripts.seed        # idempotent; seeds the catalogue
```

Seed the catalogue before pointing Vercel at the API, or the storefront's
prerender step will fetch an empty database.

To roll forward on a schema change, use a second Railway service (or a local
run) as a migration job rather than an init container, so a failed migration
halts the release instead of crash-looping the API.

---

## 8. CORS

Configured through `CORS_ORIGINS` only. No wildcard: a config validator rejects
`*` outright at startup.

| Environment | `CORS_ORIGINS` |
|---|---|
| local | `http://localhost:3000` |
| production | `https://your-app.vercel.app` |

Add the value *after* you know the Vercel domain, then redeploy. If the domain
changes, update the variable and redeploy — a stale origin list fails closed.

In practice the storefront calls the API **server-side only**, so CORS is
defence in depth rather than a functional requirement. Vercel preview domains are
per-deployment; add a pattern for them if you want previews to work.

---

## 9. Local development

Prerequisites: Python 3.13, Node 20+, PostgreSQL 14+.

```powershell
# 1. infrastructure: isolated Postgres on 55432, Redis on 6379
powershell -ExecutionPolicy Bypass -File scripts\local-services.ps1 start

# 2. backend
scripts\setup-backend.cmd
.\.venv\Scripts\python.exe -m alembic upgrade head
.\.venv\Scripts\python.exe -m scripts.seed
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --port 8000

# 3. frontend
scripts\setup-frontend.cmd
cp .env.example .env.local      # Git Bash / WSL; Copy-Item in PowerShell
npm run dev
```

`frontend/.env.local` and the repo-root `.env` are both git-ignored. VS Code
users can run **Full stack (API + frontend)** from the Run panel, which
pre-launches the infrastructure task.

---

## 10. Production build commands

```bash
# frontend
cd frontend
npm ci
npx tsc --noEmit          # 0 errors
npm run lint              # 0 errors, 0 warnings
npm run build             # requires NEXT_PUBLIC_API_URL + NEXT_PUBLIC_SITE_URL
npm run test              # 173 unit tests

# backend
cd backend
python -m pip install -e ".[dev]"
python -m ruff check app tests     # clean
python -m pytest -q               # 293 tests
```

---

## 11. Health check

`GET /health` — lightweight, no payment, email, auth or cart required. Returns
`200 {"status":"ok","version":"1.0.0"}`.

`GET /health/ready` — deeper: reports `postgres`, `redis`, `redis_jobs`,
`supabase`, `razorpay` and `email` individually. Unconfigured integrations report
`degraded` and the overall status is `degraded`; the service is still up. Use
`/health` for the platform healthcheck, since `/health/ready` is `degraded` on a
correctly-configured catalogue-only deployment.

---

## 12. Common deployment errors

| Error | Cause | Fix |
|---|---|---|
| `The Dockerfile failed validation` | no Dockerfile at the configured root | root directory must be `backend`; `railway.json` is now present |
| `Missing required environment variable NEXT_PUBLIC_API_URL` | variable not set on Vercel | add to Production **and** Preview, then redeploy |
| `Error occurred prerendering page "/"` | API unreachable from the build | deploy the API first; confirm the domain is live |
| `Refusing to start in production with an unsafe configuration` | see the listed variable | the message names every missing item |
| `PAYMENTS_ENABLED is set, so RAZORPAY_KEY_ID ... required` | payments enabled without credentials | supply them, or leave payments disabled |
| 502 from the storefront's dynamic routes | API restarted, or CORS/stale domain | check `/health` on the Railway domain |
| Canonical/OG tags point at localhost | `NEXT_PUBLIC_SITE_URL` unset or stale | set it to the deployed domain and redeploy |
| Migrations never run in production | by design | run `railway run alembic upgrade head` as a release step |
| `npm run build` works locally but fails on Vercel | `.env.local` exists locally and is git-ignored | Vercel has no `.env.local`; set the variables in the dashboard |

---

## 13. Blockers requiring a human decision or credential

| # | Blocker | Who |
|---|---|---|
| 1 | Railway account and project | you |
| 2 | Railway root directory set to `backend` | you |
| 3 | Vercel project with root directory `frontend` | you |
| 4 | Railway PostgreSQL plugin, then `alembic upgrade head` + seed | you |
| 5 | The real Vercel domain, to set `CORS_ORIGINS` | after step 3 |
| 6 | `SUPABASE_SERVICE_ROLE_KEY` for `APP_ENV=production` | you |
| 7 | Whether to relax `APP_ENV` for a demo, or supply a Supabase project | your call |
| 8 | The Railway domain, to set `NEXT_PUBLIC_API_URL` | after step 4 |
| 9 | Docker build verification | not possible here — Docker was not installed |
| 10 | Catalogue is 106 of 152 products; all product images are generated placeholders labelled `PLACEHOLDER ARTWORK` | see `docs/CONTENT_PENDING.md` |
| 11 | Cart is still browser-local; checkout cannot complete | see `docs/COMMERCE_IMPLEMENTATION_REPORT.md` |

Item 10 and 11 are not deployment problems, but a public showcase will show
placeholder product artwork and a cart that cannot check out. Both are documented
rather than hidden.
