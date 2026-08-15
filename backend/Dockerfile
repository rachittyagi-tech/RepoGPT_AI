# =============================================================================
# backend/Dockerfile
#
# Multi-stage build for RepoGPT AI's FastAPI backend (Step 14).
#
# Stage 1 (builder): installs dependencies into a virtualenv, so build
#   toolchains (gcc, etc. — needed by some Python C-extension wheels) never
#   ship in the final image.
# Stage 2 (runtime): copies only the venv + application code onto a slim
#   base, runs as a non-root user, and defaults to a production Gunicorn +
#   Uvicorn-worker command. `docker-compose.yml` (dev) overrides this
#   command with `uvicorn --reload`; `docker-compose.prod.yml` uses this
#   default as-is.
# =============================================================================

# ---------------------------------------------------------------------------
# Stage 1: builder
# ---------------------------------------------------------------------------
FROM python:3.12-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Build-time system deps only — not present in the final image.
# git: required at runtime by GitPython (Step 3) to clone repositories,
#   so it's re-installed (much smaller, no -dev/-headers) in the runtime
#   stage below rather than carried over from here.
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /build

RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# ---------------------------------------------------------------------------
# Stage 2: runtime
# ---------------------------------------------------------------------------
FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:$PATH" \
    APP_HOME=/app

# git: needed by GitPython (repository cloning, Step 3).
# curl: used by the HEALTHCHECK below.
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Non-root user — the app never needs root inside the container.
RUN groupadd --gid 1000 repogpt && \
    useradd --uid 1000 --gid repogpt --shell /bin/bash --create-home repogpt

COPY --from=builder /opt/venv /opt/venv

WORKDIR ${APP_HOME}
COPY --chown=repogpt:repogpt . .

# Persistent data directories (Step 14) — these are the two paths
# docker-compose mounts named volumes onto, so cloned repositories and the
# ChromaDB index survive container restarts/recreates. Created + owned by
# the non-root user up front so a fresh volume mount doesn't need root to
# initialize it at runtime.
RUN mkdir -p ${APP_HOME}/data/repositories ${APP_HOME}/data/chroma_db ${APP_HOME}/logs && \
    chown -R repogpt:repogpt ${APP_HOME}/data ${APP_HOME}/logs

USER repogpt

EXPOSE 8000

# Liveness check — hits the dependency-free /health endpoint (Step 14),
# not /api/health, so a slow DB never marks a perfectly-alive process unhealthy.
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Production default: Gunicorn managing Uvicorn workers (ASGI). `--workers`
# is intentionally modest (2) as a safe default for small/medium deployments —
# tune via the `WEB_CONCURRENCY` env var override below or in your platform's
# service definition. `docker-compose.yml` (dev) overrides this whole CMD
# with `uvicorn main:app --reload` for hot-reloading.
CMD ["sh", "-c", "gunicorn main:app --worker-class uvicorn.workers.UvicornWorker --workers ${WEB_CONCURRENCY:-2} --bind 0.0.0.0:8000 --timeout 120 --access-logfile - --error-logfile -"]
