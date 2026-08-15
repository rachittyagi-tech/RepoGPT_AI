# =============================================================================
# frontend/Dockerfile
#
# Multi-stage build for RepoGPT AI's React + TypeScript + Vite frontend
# (Step 14). Two independent targets, selected via `docker compose build`'s
# `target:` — see docker-compose.yml (dev) vs docker-compose.prod.yml.
#
#   `dev`        — Node + Vite dev server with HMR, source bind-mounted in
#                   from docker-compose.yml for live editing.
#   `production` — final stage: static build served by Nginx (also handles
#                   SPA routing + API reverse-proxy — see nginx.conf).
# =============================================================================

# ---------------------------------------------------------------------------
# Stage: deps — installs node_modules once, cached across the dev/build stages
# ---------------------------------------------------------------------------
FROM node:20-alpine AS deps

WORKDIR /app

COPY package.json package-lock.json* ./
RUN npm ci

# ---------------------------------------------------------------------------
# Stage: dev — local development target (docker-compose.yml)
# ---------------------------------------------------------------------------
FROM node:20-alpine AS dev

WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY . .

EXPOSE 5173
CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0"]

# ---------------------------------------------------------------------------
# Stage: build — compiles the production static bundle
# ---------------------------------------------------------------------------
FROM node:20-alpine AS build

WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY . .

# Vite bakes VITE_* variables into the bundle at BUILD time (not runtime),
# so this has to be a build ARG, passed via docker-compose.prod.yml's
# `build.args`, not a container environment variable.
ARG VITE_API_BASE_URL=http://localhost:8000
ENV VITE_API_BASE_URL=${VITE_API_BASE_URL}

RUN npm run build

# ---------------------------------------------------------------------------
# Stage: production — Nginx serving the static build (final/default stage)
# ---------------------------------------------------------------------------
FROM nginx:1.27-alpine AS production

# Non-root: nginx:alpine already ships an unprivileged `nginx` user; we
# just need to make sure it owns everything it writes to.
COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf

RUN chown -R nginx:nginx /usr/share/nginx/html && \
    chown -R nginx:nginx /var/cache/nginx && \
    touch /var/run/nginx.pid && \
    chown nginx:nginx /var/run/nginx.pid

USER nginx

EXPOSE 80

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD wget -q --spider http://localhost:80/ || exit 1

CMD ["nginx", "-g", "daemon off;"]
