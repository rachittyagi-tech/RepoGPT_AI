# 🧠 RepoGPT AI

**Intelligent GitHub Repository Chat & Code Analysis Platform**

RepoGPT AI lets developers connect a public GitHub repository and "chat" with
it — asking questions about architecture, functions, and design decisions —
via a Retrieval-Augmented Generation (RAG) pipeline over the repository's
actual source code. It also runs AI-powered code review, security/performance
analysis, README/documentation generation, and repository analytics.

> **Status:** Steps 1–14 complete — auth, repository ingestion, RAG chat,
> analytics dashboard, AI code intelligence engine, and containerized
> deployment are all implemented. Step 15 (final testing, security audit,
> performance tuning) is next.

---

## 📋 Table of Contents

1. [Project Overview](#-project-overview)
2. [Features](#-features)
3. [Architecture](#-architecture)
4. [Tech Stack](#-tech-stack)
5. [Folder Structure](#-folder-structure)
6. [Local Development](#-local-development)
7. [Docker Development](#-docker-development)
8. [Environment Variables](#-environment-variables)
9. [Database Setup & Migrations](#-database-setup--migrations)
10. [Running Tests](#-running-tests)
11. [CI/CD](#-cicd)
12. [Production Build & Deployment](#-production-build--deployment)
13. [Backup Strategy](#-backup-strategy)
14. [Monitoring Readiness](#-monitoring-readiness)
15. [Security Checklist](#-security-checklist)
16. [Troubleshooting](#-troubleshooting)
17. [License](#-license)

---

## 🎯 Project Overview

RepoGPT AI clones a public GitHub repository, scans and chunks its source
code, generates embeddings, stores them in ChromaDB, and exposes a
citation-grounded chat interface backed by Google Gemini. On top of that, an
AI Code Intelligence Engine provides code review, bug/security/performance
analysis, and README/documentation generation — all grounded in retrieved
code, never freely hallucinated.

## ✨ Features

- 🔐 Email/password auth with JWT access + refresh tokens, RBAC
- 📥 Public GitHub repo ingestion (clone → scan → chunk → embed → index)
- 💬 Context-aware chat over an entire codebase (RAG), streamed via SSE
- 📊 Analytics dashboard — per-repo health score, language breakdown, index
  status, AI usage insights
- 🕵️ AI Code Intelligence — code review, bug detection, security scanning,
  performance analysis, README/API-doc generation, architecture explanation,
  repository quality score
- 🗂️ Multi-repository, multi-conversation chat history
- 🐳 Fully containerized, with separate dev/prod Docker Compose stacks

## 🏗️ Architecture

```
                    ┌─────────────────────────┐
                    │   React + TS Frontend    │
                    │  (Vite dev / Nginx prod) │
                    └────────────┬─────────────┘
                                 │ REST + SSE (axios / fetch)
                    ┌────────────▼─────────────┐
                    │   Nginx (prod only)       │
                    │  static files + /api proxy│
                    └────────────┬─────────────┘
                                 │
                    ┌────────────▼─────────────┐
                    │   FastAPI Backend         │
                    │  Auth·Repos·RAG·Chat·     │
                    │  Analytics·Intelligence   │
                    └───┬──────────┬───────────┘
                        │          │
             ┌──────────▼──┐   ┌───▼─────────────┐
             │ PostgreSQL  │   │ ChromaDB          │
             │ (users,     │   │ (embedded,        │
             │  sessions)  │   │  persistent dir)  │
             └─────────────┘   └───────────────────┘
                        │
             ┌──────────▼──────────┐    ┌─────────────────┐
             │ Local repo storage  │    │  Google Gemini   │
             │ (cloned repos)      │    │  (chat + embed)  │
             └──────────────────────┘    └─────────────────┘
```

ChromaDB runs **embedded** (`PersistentClient`) inside the backend process —
it is not a separate network service. Its data directory and the cloned-repo
directory are the two things that must be on persistent storage/volumes.

## 🛠️ Tech Stack

**Backend:** Python 3.12, FastAPI, Uvicorn/Gunicorn, SQLAlchemy 2.0 (async),
PostgreSQL, Alembic, ChromaDB, Google Gemini, GitPython, JWT (python-jose),
bcrypt (passlib)

**Frontend:** React 19, TypeScript, Vite, TailwindCSS, TanStack Query, Axios,
Recharts, React Router

**Infra:** Docker, Docker Compose, Nginx, GitHub Actions

## 📁 Folder Structure

```
repogpt-ai/
├── backend/
│   ├── app/
│   │   ├── api/            # FastAPI routers (auth, github, chat, analytics, intelligence, ...)
│   │   ├── services/       # Business logic — one service per concern
│   │   ├── models/         # SQLAlchemy ORM models (User, RefreshToken, LoginSession)
│   │   ├── schemas/        # Pydantic request/response DTOs
│   │   ├── prompts/        # Gemini prompt templates
│   │   ├── core/           # Settings, constants, exceptions, logging, security
│   │   ├── database/       # Async Postgres session + ChromaDB client
│   │   └── middleware/     # Request ID, timing, structured logging
│   ├── alembic/             # DB migrations
│   ├── tests/
│   ├── Dockerfile
│   ├── requirements.txt
│   └── pyproject.toml       # ruff / black / mypy / pytest config
├── frontend/
│   ├── src/
│   │   ├── pages/           # Route-level views
│   │   ├── components/      # UI, organized by feature
│   │   ├── hooks/           # React Query hooks
│   │   ├── services/        # Axios API clients
│   │   └── types/           # TypeScript types mirroring backend schemas
│   ├── Dockerfile            # multi-stage: dev (Vite) / production (Nginx)
│   ├── nginx.conf
│   └── eslint.config.js
├── .github/workflows/        # ci.yml, cd.yml
├── docker-compose.yml         # dev stack
├── docker-compose.prod.yml    # production stack
├── .env.example                # full variable reference
├── .env.development.example
└── .env.production.example
```

## 💻 Local Development

**Prerequisites:** Python 3.12, Node 20+, PostgreSQL 16 (or use Docker for
just the DB — see below), a Gemini API key.

### Backend (bash / macOS / Linux)
```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp ../.env.development.example ../.env   # then edit values, especially GEMINI_API_KEY
alembic upgrade head
uvicorn main:app --reload
```

### Backend (PowerShell / Windows)
```powershell
cd backend
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item ..\.env.development.example ..\.env
alembic upgrade head
uvicorn main:app --reload
```

### Frontend (either OS)
```bash
cd frontend
npm install
npm run dev
```
Backend: `http://localhost:8000` (docs at `/docs`). Frontend: `http://localhost:3000`.

If you don't want to install Postgres locally, run just the DB via Docker:
```bash
docker compose up db -d
```

## 🐳 Docker Development

Runs backend (hot-reload), frontend (Vite dev server + HMR), and Postgres.
ChromaDB is embedded in the backend container (no separate service) and
persists via the bind-mounted `./backend:/app` volume.

```bash
cp .env.development.example .env   # edit GEMINI_API_KEY at minimum
docker compose up --build
```

- Frontend: `http://localhost:3000`
- Backend: `http://localhost:8000`
- Postgres: `localhost:5432`

Stop and remove containers: `docker compose down` (add `-v` to also drop the
Postgres volume — cloned repos/ChromaDB data live in the bind-mounted
`backend/data/` folder either way, so `-v` doesn't touch those).

> **Note:** the original scaffold's `docker-compose.yml` referenced a
> standalone `chromadb` HTTP service and a `worker` (Celery) service.
> Neither is used by any implemented code — ChromaDB runs embedded, and no
> Celery app module exists — so both were removed rather than shipped
> broken. See the comment block at the top of `docker-compose.yml`.

## 🔑 Environment Variables

Full reference with explanations: **`.env.example`**. Environment-specific
starting points: `.env.development.example` / `.env.production.example`.

Key variables:

| Variable | Purpose |
|---|---|
| `APP_ENV` | `development` \| `staging` \| `production` |
| `SECRET_KEY` / `JWT_SECRET_KEY` | App + JWT signing secrets — generate with `openssl rand -hex 32` |
| `DATABASE_URL` | Async Postgres URL (`postgresql+asyncpg://...`) |
| `GEMINI_API_KEY` / `GEMINI_MODEL` | Chat generation |
| `EMBEDDING_PROVIDER` | `huggingface` (local, no key) or `gemini` |
| `CHROMA_PERSIST_DIR` | Local directory for the embedded ChromaDB store |
| `REPOSITORY_STORAGE_PATH` | Where cloned repos are written |
| `ALLOWED_ORIGINS` | Comma-separated exact CORS origins — **never `*` in production** |
| `FRONTEND_URL` / `BACKEND_URL` | Cross-service links |
| `LOG_JSON` | `true` in production for structured/parseable logs |
| `VITE_API_BASE_URL` | Frontend build-time API base — empty string = same-origin (Nginx-proxied) |

**Never commit** `.env`, `.env.production`, or `.env.development` — only the
`*.example` templates are tracked (see `.gitignore`).

## 🗄️ Database Setup & Migrations

```bash
cd backend

# Create a new migration after changing a model
alembic revision --autogenerate -m "describe the change"

# Apply all pending migrations
alembic upgrade head

# Check current migration status
alembic current
alembic history

# Roll back one migration
alembic downgrade -1
```

Always review autogenerated migrations before applying — Alembic's
diffing is a starting point, not a guarantee.

## 🧪 Running Tests

```bash
cd backend
pytest --cov=app --cov-report=term-missing
```

Lint/format/type-check (same checks CI runs):
```bash
ruff check .
black --check .
mypy app
```

Frontend:
```bash
cd frontend
npm run lint
npm run build   # also runs `tsc -b` type-checking
```

## 🔄 CI/CD

- **`.github/workflows/ci.yml`** — on every push/PR to `main`/`develop`:
  installs backend deps, lints (ruff), format-checks (black), type-checks
  (mypy), runs pytest against a real Postgres service container, builds the
  backend Docker image; installs frontend deps, lints, builds (which
  type-checks via `tsc -b`), builds the frontend Docker image. Any failure
  fails the whole job.
- **`.github/workflows/cd.yml`** — builds and pushes versioned Docker images
  to GHCR after CI passes on `main`. Deployment jobs for both options below
  are included as **disabled stubs** (`if: false`) — flip to `true` and add
  the listed secrets once you've picked a target.

## 🚀 Production Build & Deployment

### Option A — Vercel (frontend) + Render (backend + Postgres)
**Recommended for getting started fast / small teams.** Vercel's CDN is
excellent for the static frontend; Render manages Postgres backups and
zero-downtime deploys for you. Less infra to operate, but two platforms to
configure and slightly more moving parts for CORS (frontend and backend are
on different origins — set `VITE_API_BASE_URL` to the Render backend URL and
`ALLOWED_ORIGINS` to the Vercel URL).

1. **Backend → Render:** New Web Service from this repo, root directory
   `backend`, Docker runtime (uses `backend/Dockerfile`, `runtime` stage).
   Add all backend env vars from `.env.production.example`. Add a Render
   PostgreSQL instance and set `DATABASE_URL` to its connection string.
2. **Database → Render PostgreSQL:** create the instance, then run
   `alembic upgrade head` once (Render's shell, or a one-off job) before
   first use.
3. **Frontend → Vercel:** import this repo, root directory `frontend`,
   framework preset "Vite". Set `VITE_API_BASE_URL` to your Render backend's
   URL in Vercel's project env vars (build-time).

### Option B — Full Docker deployment
**Recommended once you have your own VM/server (or a managed container
host).** Single `docker compose -f docker-compose.prod.yml up -d` brings up
everything on one origin (Nginx proxies `/api/` to the backend), which keeps
CORS trivial (`VITE_API_BASE_URL` stays empty). More operational
responsibility (you patch the host, manage TLS, etc.) in exchange for full
control and no cross-platform CORS complexity.

```bash
cp .env.production.example .env.production   # fill in every CHANGE-ME value
docker compose -f docker-compose.prod.yml --env-file .env.production up -d --build
docker compose -f docker-compose.prod.yml exec backend alembic upgrade head
```

Put your own TLS-terminating reverse proxy (or a managed load balancer) in
front of port 80, or extend `frontend/nginx.conf` with a `listen 443 ssl`
server block and your certificates.

**Which to pick:** Option A if you want the platforms to handle scaling,
backups, and zero-downtime deploys for you and don't mind two dashboards.
Option B if you already run infrastructure, want everything in one place,
or need full control over the stack.

## 💾 Backup Strategy

| Data | Back up? | How |
|---|---|---|
| PostgreSQL (`postgres_data` volume) | **Yes — critical.** Users, sessions, refresh tokens. | `pg_dump` on a schedule (Render PostgreSQL does this automatically; for Option B, cron a `pg_dump` from the `db` container to off-host storage). |
| ChromaDB (`chroma_data` / `data/chroma_db`) | **Recommended, not critical.** It's a rebuildable derived index (re-index from the source repos + Gemini/HF embeddings), but backing it up avoids costly re-embedding after data loss. | Periodic archive (`tar`) of the volume/directory to off-host storage. |
| Repository storage (`repositories_data` / `data/repositories`) | **Not critical — do not back up.** This is a disposable clone of public GitHub repos; it can always be re-cloned. | N/A — re-clone on demand instead. |
| `.env*` secrets | **Never commit to Git.** Store in your platform's secret manager (Render env vars, GitHub Secrets) or an encrypted vault, not in a backup archive alongside application data. | — |

## 📈 Monitoring Readiness

- **Structured logs:** set `LOG_JSON=true` in production — every request log
  line includes `request_id`, `method`, `path`, `status_code`, and
  `duration_ms` as real JSON fields (see `app/core/logging.py` /
  `app/middleware/middleware.py`), ready to ship to any log aggregator
  (CloudWatch, Loki, Datadog, etc.) without extra instrumentation.
- **Health/readiness:** `GET /health` (liveness, no dependencies — safe for
  frequent polling) and `GET /api/health` (readiness — checks Postgres,
  ChromaDB, and basic config; returns HTTP 503 when degraded, without
  exposing secret values).
- **Error monitoring:** `SENTRY_DSN` is a reserved env var — wire up the
  `sentry-sdk` FastAPI integration if/when you adopt Sentry; not added by
  default to avoid a mandatory paid dependency.
- **Metrics:** no metrics library is bundled by default (kept dependency-light
  per Step 14's scope) — the structured request logs above already give you
  latency/status-code data to build dashboards from your log aggregator,
  and are the natural place to add a Prometheus exporter later if needed.

## 🔒 Security Checklist

- [ ] `SECRET_KEY` / `JWT_SECRET_KEY` are long, random, and **different** from each other and from any example value
- [ ] `.env`, `.env.production`, `.env.development` are gitignored and never committed (verify: `git check-ignore .env.production`)
- [ ] `ALLOWED_ORIGINS` lists exact production origins — never `*`
- [ ] `APP_DEBUG=false` and `LOG_JSON=true` in production
- [ ] Postgres password is strong and unique; not reused from `.env.example`
- [ ] Containers run as non-root (already default in `backend/Dockerfile` / `frontend/Dockerfile`)
- [ ] GHCR/registry images are private if the repo/code is proprietary
- [ ] GitHub Secrets (not repo variables) hold every credential referenced in `cd.yml`
- [ ] TLS is terminated somewhere in front of production traffic (platform-provided on Option A; you configure it for Option B)
- [ ] `GET /api/health` never returns secret values — only booleans (verify after any change to that endpoint)

## 🩺 Troubleshooting

**`docker compose up` fails on the `db` healthcheck.**
Postgres can take a few seconds on first boot (initializing the data
directory). Wait, or check `docker compose logs db`.

**Backend can't connect to the database.**
Confirm `DATABASE_URL`'s host matches the Compose service name (`db`) when
running in Docker, or `localhost` when running the backend directly on your
host machine against a Dockerized Postgres.

**`GET /api/health` returns `"database": false`.**
Check `DATABASE_URL` and that migrations have been applied
(`alembic upgrade head`) — a missing `users` table will fail queries even
if the connection itself succeeds.

**ChromaDB data seems to disappear after a restart.**
In dev, confirm the `./backend:/app` bind mount is actually active
(`docker compose config` to inspect resolved volumes). In prod, confirm the
`chroma_data` named volume is attached to the `backend` service in
`docker-compose.prod.yml` — don't run `docker compose down -v`, which
deletes named volumes.

**Frontend can't reach the backend (CORS or network errors).**
In Docker dev, the frontend talks to `http://localhost:8000` directly from
the browser (not through Nginx) — confirm `ALLOWED_ORIGINS` includes
`http://localhost:3000`. In Option B production, the frontend's Nginx
proxies `/api/` internally — confirm `VITE_API_BASE_URL` was built as an
empty string and that the `frontend` container's `depends_on: backend` let
Nginx resolve the `backend` hostname at startup (restart `frontend` if it
started before `backend` was ready).

**Streaming chat responses arrive all at once instead of token-by-token.**
This means something between the browser and FastAPI is buffering the SSE
response. Check `frontend/nginx.conf`'s `/api/` location has
`proxy_buffering off`, and that no CDN/extra proxy in front of it re-enables
buffering.

**`npm run lint` fails with "no configuration found."**
Make sure you're on the version of `frontend/eslint.config.js` introduced in
Step 14 — earlier scaffolds had no ESLint 9 flat config at all.

**`MAX_RETRIES` env var doesn't seem to do anything.**
As of Step 14 it's split into `EMBEDDING_MAX_RETRIES` and
`GEMINI_CHAT_MAX_RETRIES` — the two previously silently shared one
`MAX_RETRIES` variable, so setting it only ever affected whichever service's
`BaseSettings` happened to load last.

## 📄 License

MIT — see [LICENSE](./LICENSE) if present, or add one before making the
repository public.
