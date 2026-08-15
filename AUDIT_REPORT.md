# RepoGPT AI — Step 15 Final Engineering Audit

**Methodology:** direct code inspection (not a generic checklist) — every
finding below was confirmed by reading the actual implementation, grepping
for the specific pattern, or tracing a call path. Live end-to-end testing
against a running Postgres/ChromaDB/Gemini stack was not possible in this
environment (no network access, no provisioned services), so this is a
**static audit** — Step 16 should include a real integration-test pass
against a live stack before calling the platform launch-ready.

---

## 🔴 Critical — found, requires a coordinated fix (not applied yet)

### No authentication/authorization enforcement, no ownership model
**Evidence:** `grep -rn "get_current_user" app/api/*.py` matches only
`auth.py` and `users.py`. Every other router — `github`, `scanner`,
`chunking`, `embeddings`, `vector_store`, `rag`, `chat`, `analytics`,
`intelligence` — has zero auth dependency anywhere.

**Why this matters:**
- Anyone, with no login at all, can clone repositories, run the full
  ingestion pipeline, chat with any indexed repo, and run every AI
  Code Intelligence endpoint (each of which costs a real Gemini API call).
- There is no `Repository` ownership record anywhere in the data model.
  Repositories are identified purely by `owner__repo` (derived from the
  GitHub URL, see `app/utils/github_validator.py:build_folder_name`) —
  the same string for every user. Two different platform accounts cloning
  the same public repo get the **identical** local clone directory and
  the **identical** ChromaDB collection.
- `Conversation` records (`app/services/conversation_service.py`) are
  keyed by `conversation_id` + `repository_name`, not by user — nothing
  stops one client from reading another's conversation by ID.

**Why I did not fix this unilaterally:** I checked the frontend
(`grep -rn "Authorization\|Bearer\|access_token" frontend/src`) — there is
**no login page, no token storage, and no axios interceptor anywhere**.
Adding `Depends(get_current_user)` to these routers right now would return
401 on every single existing page and break the working application
outright, which conflicts with this step's own "do not remove existing
functionality" constraint. This needs to land as one coordinated change,
not a silent backend-only flip.

**Recommended remediation (Step 16 scope):**
1. Add a `Repository` ORM table (`id`, `owner_user_id` FK, `repository_name`,
   `github_url`, timestamps) — migrate via Alembic.
2. Namespace ChromaDB collections and local clone paths by
   `{user_id}__{owner}__{repo}` instead of `{owner}__{repo}`, so two users
   cloning the same public repo get fully independent storage.
3. Add `user_id` to `Conversation` and filter every read by
   `conversation.user_id == current_user.id`.
4. Add `dependencies=[Depends(get_current_user)]` to every router listed
   above, in the same change that ships (1)-(3) and the frontend auth flow
   below — not before, or the app breaks.
5. Frontend: build a login/register page, store the access token (memory +
   refresh-token-based silent renewal, not `localStorage` for the access
   token if avoidable), and add an axios request interceptor that attaches
   `Authorization: Bearer <token>` and a response interceptor that calls
   `/api/auth/refresh` on a 401 before retrying once.

---

## ✅ Fixed this step

### 1. Path traversal via `repository_name` (CWE-22)
**Where:** `app/services/scanner_service.py` (`scan_repository`) and
`app/services/dependency_service.py` (`analyze`) built
`base_dir / repository_name` directly from request input with **no**
validation — unlike `app/services/github_service.py`, which already calls
`is_safe_repository_name()` on every path it builds.

**Impact:** `repository_name = "../../../../etc"` sent to
`POST /api/scanner/scan` or (via `dependency_service`)
`POST /api/intelligence/security` could read files outside
`REPOSITORIES_BASE_DIR`.

**Fix:** both methods now call the existing
`app.utils.github_validator.is_safe_repository_name()` guard before
touching the filesystem, raising the same `RepositoryPathNotFoundError` /
`RepositoryNotFoundError` the rest of the codebase already uses for an
unknown repository — no new exception type, no behavior change for valid
repository names.

**Not affected:** `readme_generator.py`'s license-file lookup also builds
`base_dir / repository_name`, but `generate()` calls
`github_service.get_repository_status()` first, which already validates —
confirmed safe, left unchanged.

### 2. Password-reset token logged in production
**Where:** `POST /api/auth/forgot-password` logged the raw reset token
(a bearer credential — possessing it lets anyone reset that account's
password without the old one) unconditionally at INFO level.

**Impact:** with `LOG_JSON=true` in production (Step 14), this token would
ship straight into whatever log aggregator is configured — a real
account-takeover vector for anyone with log read access.

**Fix:** now only logs in non-production
(`if reset_token and not settings.is_production`). No email-delivery
integration exists yet, so there's currently no way to hand this token to
the user in production at all — that gap is real but pre-existing and
out of scope here; flagged for a future step ("wire up transactional email").

### 3. No rate limiting anywhere
**Where:** none of the 9 non-auth routers, nor `auth.py` itself, had any
throttling — meaning unlimited repository clones, unlimited Gemini-backed
chat/AI-intelligence calls (real cost), and unlimited login attempts
(brute force).

**Fix:** added `app/middleware/rate_limit.py` — a dependency-free,
in-memory sliding-window limiter (no new package, no Redis requirement,
consistent with the process-local `ClassVar` cache pattern already used
throughout this codebase). Applied per-router via
`APIRouter(dependencies=[Depends(rate_limit(bucket, n, seconds))])`:

| Router | Limit |
|---|---|
| `auth` | 10 / 60s / IP |
| `github` | 10 / 60s / IP |
| `scanner`, `chunking`, `embeddings`, `vector_store` | 10 / 60s / IP each |
| `rag` | 20 / 60s / IP |
| `chat` | 20 / 60s / IP |
| `intelligence` | 10 / 60s / IP |

Honors `X-Forwarded-For` (set by the production Nginx, Step 14) so the
limiter keys on the real client IP, not the proxy's.

**Known limitation, stated plainly:** this is in-memory and per-process —
correct for the current single-backend-instance deployment
(`docker-compose.prod.yml`), but will NOT correctly share limits across
multiple backend replicas. If you scale the backend horizontally, swap the
`_SlidingWindowLimiter`'s in-memory dict for a Redis-backed sorted-set
implementation behind the same `rate_limit()` interface.

---

## ✅ Verified clean — no fix needed

- **Secrets scanning:** grepped source for hardcoded API keys, passwords,
  tokens, private-key blocks — none found. No `.env`/`.env.production`
  files are committed. `.gitignore` correctly excludes them (fixed in
  Step 14).
- **Error handling:** the global `unhandled_exception_handler`
  (`app/core/exceptions.py`) already returns a generic message and never
  leaks `str(exc)`, stack traces, or file paths to the client — full
  detail only goes to `logger.exception()` server-side. `/docs`, `/redoc`,
  `/openapi.json` are already disabled when `APP_ENV=production`.
- **Command injection:** repository cloning uses GitPython's
  `Repo.clone_from()` (argument-list subprocess invocation, not a shell
  string) — no `shell=True` anywhere in the codebase.
- **SSRF via repository URL:** `GITHUB_URL_PATTERN` hardcodes the host to
  `github.com`/`www.github.com` — there's no way to make the backend clone
  from or make a request to an arbitrary/internal host.
- **ChromaDB cross-repository isolation:** every read/write/search goes
  through `_build_collection_name(repository_name)`, giving each
  repository name its own dedicated collection — Repository A genuinely
  cannot retrieve Repository B's vectors. (The gap is per-*user*
  isolation, covered in the Critical section above, not this technical
  isolation, which is correctly implemented.)
- **N+1 queries:** `User.refresh_tokens` / `User.login_sessions`
  relationships use `lazy="selectin"` (eager, batched) — no per-row query
  loop. No other DB-backed list endpoints exist yet (repositories/
  conversations are in-memory, not DB-backed, in the current architecture).
- **DB constraints:** `username`/`email` are `unique=True` + indexed;
  `refresh_tokens.jti` is `unique=True` + indexed; both FKs to `users.id`
  use `ondelete="CASCADE"` — deleting a user correctly cascades to their
  sessions/tokens.
- **Frontend XSS:** no `dangerouslySetInnerHTML` and no `rehype-raw`
  anywhere — `react-markdown` renders AI/chat content with raw HTML
  disabled by default, so Gemini output can't inject a `<script>` tag
  through the chat UI.
- **CORS:** `ALLOWED_ORIGINS` is env-driven and never `"*"` by default
  (verified in Step 14, unchanged since).

---

## Not yet covered by this pass (recommended for Step 16)

- Live integration testing against a real Postgres + ChromaDB + Gemini
  stack (this audit was static/code-only — no network access here).
- Frontend testing (login/register/dashboard/chat/analytics UI flows,
  loading/error/empty states, responsive layout) — blocked on the
  Critical finding above (there's no login UI to test yet).
- Full Alembic migration upgrade/downgrade dry-run against a fresh DB.
- Load/performance testing (response times under concurrent chat/indexing
  load, embedding batch throughput, large-repository indexing time).
- Docker image size audit (`docker images` + `dive` or similar).
