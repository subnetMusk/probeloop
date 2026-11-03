# 0008 — Docker Compose as the runtime and development environment

- Status: Accepted
- Date: 2026-11-03

## Context

The development machine runs Windows with an NVIDIA GPU. A future machine is an Apple Silicon
laptop. Running natively would mean supporting three operating systems, installing CUDA DLLs on
Windows, and keeping current Node and `uv` versions on every host. Piper must run as a separate
program for licensing reasons (ADR 0007). Speech recognition needs its own resource limits so that
it does not starve the backend or the LLM.

## Decision

Docker Compose is the supported way to run and develop ProbeLoop.

**Services**

| Service | Role |
|---|---|
| `backend` | FastAPI app; serves the built SPA at runtime |
| `stt-worker` | ProbeLoop speech worker; CPU and CUDA image variants |
| `tts-piper` | Unmodified Piper HTTP server |
| `ollama` | Profile `nvidia`, with a GPU reservation |
| `postgres` | Profile `postgres` |
| `frontend-dev` | Vite with HMR, development only |

**Volumes**

- `data`: database, blobs, audio.
- `models`: speech models and voices.
- `ollama`: LLM models.

**Rules**

- **Publishing.** Only the backend is published, and only on `127.0.0.1`.
- **Networking.** Internal services sit on an internal network.
- **Hardening.**
  - Containers run as a non-root user, with `cap_drop: [ALL]` and `no-new-privileges`, and they
    are read-only where possible.
  - The Docker socket is never mounted into an application service.
- **Development.** `docker compose watch` syncs files instead of using bind mounts. Tests and
  checks run inside the containers.
- **Images and CI.** Images are multi-arch (amd64 and arm64). CI runs on ubuntu only.
- **External Ollama.** An Ollama outside Compose remains supported through `OLLAMA_BASE_URL`:
  native on the host via `host.docker.internal`, or on another machine on the LAN.

## Consequences

- The host needs only Docker and git, and the application runs on Linux everywhere.
- GPU access goes through Docker Desktop and WSL2. This must be verified in M1, with native
  Ollama on the host as the fallback.
- On macOS, containers cannot use Metal. The LLM runs remotely, and speech recognition runs on the
  CPU or as a native worker on the host.
- The WSL2 VM's resources (`.wslconfig`) must be sized for the LLM and speech workloads.
- Models must be downloaded into volumes; the host's existing Ollama models are not reused.

## Alternatives considered

- **Native execution as the primary mode** — more platform-specific setup and support burden.
- **A single container with everything** — no isolation of the GPL component, and no per-service
  resource limits.
- **Bind-mounting source and data from NTFS** — slow file access, unreliable file watching and
  SQLite locking problems on Docker Desktop for Windows.
