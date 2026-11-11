# syntax=docker/dockerfile:1
# Build context: the repository root (see .dockerignore).

FROM python:3.13-slim AS base
COPY --from=ghcr.io/astral-sh/uv:0.13.7 /uv /usr/local/bin/uv
ENV UV_COMPILE_BYTECODE=1 \
    UV_COMPILE_BYTECODE_TIMEOUT=180 \
    UV_CONCURRENT_INSTALLS=2 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/opt/venv \
    PATH=/opt/venv/bin:$PATH \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    ORT_DISABLE_TELEMETRY=1 \
    TOKENIZERS_PARALLELISM=false
RUN useradd --create-home --uid 1000 app \
    && mkdir -p /data \
    && chown app:app /data
WORKDIR /app
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
       libpango-1.0-0 libpangoft2-1.0-0 libharfbuzz-subset0 fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/*

# The single-page app, built once and served by the backend at runtime.
FROM node:24.22.0-trixie-slim AS frontend
WORKDIR /frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN --mount=type=cache,target=/root/.npm npm ci --no-audit --no-fund
COPY frontend/ ./
RUN npm run build

# Runtime: application dependencies only, plus the built frontend.
FROM base AS runtime
ENV PROBELOOP_STATIC_DIR=/app/static
COPY backend/pyproject.toml backend/uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv uv sync --frozen --no-dev --no-install-project
COPY backend/src ./src
RUN --mount=type=cache,target=/root/.cache/uv uv sync --frozen --no-dev
COPY --from=frontend /frontend/dist ./static
USER app
EXPOSE 8000
HEALTHCHECK --interval=10s --timeout=10s --start-period=90s \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=2)"]
CMD ["uvicorn", "probeloop.api.app:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000"]

# Dev: adds the dev dependency group, the speech engines (`stt` extra, for type checks and live
# tests), tests and evals; the source is synced by `compose watch`.
# The environment is installed at build time, so `uv run` must not try to modify it.
FROM base AS dev
ENV UV_NO_SYNC=1 \
    HF_HOME=/models/hf \
    HF_HUB_OFFLINE=1 \
    HF_HUB_DISABLE_TELEMETRY=1 \
    ORT_DISABLE_TELEMETRY=1
COPY backend/pyproject.toml backend/uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv uv sync --frozen --all-extras --no-install-project
COPY --chown=app:app backend/ ./
RUN --mount=type=cache,target=/root/.cache/uv uv sync --frozen --all-extras \
    && chown app:app /app
USER app
EXPOSE 8000
CMD ["uvicorn", "probeloop.api.app:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000", "--reload", "--reload-dir", "/app/src"]
