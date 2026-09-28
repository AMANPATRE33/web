# syntax=docker/dockerfile:1
#
# Production image for the FastAPI backend.
#
# Single stage on purpose. A multi-stage build would shave a few tens of
# megabytes off an image that is dominated by asyncpg, psycopg and the crypto
# stack anyway, and it would add a second copy of the source tree to keep in
# sync. The build context is already small - see backend/.dockerignore, which is
# what actually keeps the image lean.
#
# Build with backend/ as the context root:
#     cd backend && docker build -t storefront-api .
#
# The context is backend/ rather than the repository root so the frontend, the
# docs and the 333 seed SVGs are never uploaded to the daemon, let alone
# considered for the image. The backend needs nothing outside its own directory.
# Every COPY below is therefore backend-relative.
#
# Set Railway's Root Directory to `backend` and it will use this file as-is.
# See docs/DEPLOYMENT.md.
FROM python:3.13-slim

# 3.13 is deliberate: pyproject pins requires-python >=3.12,<3.14, and asyncpg
# has no cp314 wheels, so 3.14 would fail at the asyncpg build step.

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONPATH=/srv/backend

WORKDIR /srv/backend

# Dependencies before the rest of the source, so editing a route does not
# reinstall the world. `pip install .` needs pyproject.toml *and* the app
# package present, because setuptools discovers packages from ./app. Alembic
# comes in through the same install - it is a declared dependency, so there is
# no second pip call to fall out of sync with pyproject.
COPY pyproject.toml ./
COPY app ./app
RUN pip install --no-cache-dir .

# Migrations ship with the image so they can be run as a one-off command
# (`alembic upgrade head`) rather than baked into the startup path. Running
# migrations on every container start is what causes rolling-deploy races: two
# replicas start, both migrate, and one fails on a lock.
COPY alembic ./alembic
COPY alembic.ini ./

# Run as an unprivileged user. Nothing in the container needs to write outside
# /tmp, and a container that never runs as root cannot be talked into doing so.
RUN useradd --create-home --uid 10001 appuser \
    && chown -R appuser:appuser /srv/backend
USER appuser

EXPOSE 8080

# Railway injects PORT. A JSON CMD cannot expand it, so the shell form is used
# deliberately; 8080 is only the local-default so `docker run -p 8080:8080`
# works without extra flags.
#
#   uvicorn app.main:app --host 0.0.0.0 --port $PORT
#
# Migrations are NOT run here on purpose - see the comment above.
CMD ["sh", "-c", "exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8080}"]

# Uses python rather than curl, which slim images do not ship. A failure here
# reports unhealthy, which is what the platform needs to route traffic away.
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD ["python", "-c", "import os,urllib.request,sys;\
url=f\"http://127.0.0.1:{os.environ.get('PORT','8080')}/health\";\
sys.exit(0 if urllib.request.urlopen(url, timeout=4).status==200 else 1)"]
