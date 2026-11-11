# syntax=docker/dockerfile:1
# Build context: the repository root (see .dockerignore).
# Unmodified Piper (GPL-3.0-or-later) and its built-in HTTP server, run as a separate program and
# reached over HTTP (ADR 0007, ADR 0010). Voices live in the `models` volume under /models/piper.

FROM python:3.13-slim
COPY --from=ghcr.io/astral-sh/uv:0.13.7 /uv /usr/local/bin/uv
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    ORT_DISABLE_TELEMETRY=1
COPY docker/tts-piper/requirements.txt /tmp/requirements.txt
RUN --mount=type=cache,target=/root/.cache/uv \
    uv pip install --system --require-hashes -r /tmp/requirements.txt \
    && rm /tmp/requirements.txt
RUN useradd --create-home --uid 1000 piper \
    && mkdir -p /models/piper \
    && chown -R piper:piper /models
USER piper
COPY docker/tts-piper/wait-for-voice.py /usr/local/bin/wait-for-voice.py
WORKDIR /home/piper
EXPOSE 5000
HEALTHCHECK --interval=10s --timeout=3s --start-period=30s --retries=3 \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:5000/voices', timeout=2)"]
ENTRYPOINT ["python", "/usr/local/bin/wait-for-voice.py"]
CMD ["-m", "it_IT-serena-medium"]
