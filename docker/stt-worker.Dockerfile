# syntax=docker/dockerfile:1
# Build context: the repository root (see .dockerignore).
# The stt-worker is the same Python package as the backend, with the `stt` extra and a different
# entrypoint. `cpu` is the only variant: M1 put speech recognition on the CPU (ADR 0009).

FROM python:3.13-slim AS cpu
COPY --from=ghcr.io/astral-sh/uv:0.13.7 /uv /usr/local/bin/uv
ENV UV_COMPILE_BYTECODE=1 \
    UV_COMPILE_BYTECODE_TIMEOUT=180 \
    UV_CONCURRENT_INSTALLS=2 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/opt/venv \
    PATH=/opt/venv/bin:$PATH \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    HF_HOME=/models/hf \
    HF_HUB_OFFLINE=1 \
    HF_HUB_DISABLE_TELEMETRY=1 \
    ORT_DISABLE_TELEMETRY=1
RUN useradd --create-home --uid 1000 app \
    && mkdir -p /models \
    && chown app:app /models
WORKDIR /app
COPY backend/pyproject.toml backend/uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --extra stt --no-install-project
COPY backend/src ./src
RUN --mount=type=cache,target=/root/.cache/uv uv sync --frozen --no-dev --extra stt
COPY LICENSE NOTICE THIRD_PARTY_NOTICES.md /usr/share/doc/probeloop/
USER app
EXPOSE 8000
# Loading Parakeet from the models volume takes about 25 s on a cold cache.
HEALTHCHECK --interval=10s --timeout=3s --start-period=120s --retries=3 \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=2)"]
CMD ["python", "-m", "probeloop.speech.worker", "serve"]
