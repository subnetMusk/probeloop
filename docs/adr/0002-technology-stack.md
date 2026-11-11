# 0002 — Technology stack

> **Decision record.** Current implementation guidance is in [architecture](../architecture.md) and [configuration](../configuration.md); later ADRs amend specific decisions.

- Status: Accepted
- Date: 2026-11-03

## Context

The machine-learning ecosystem (speech recognition, PDF handling, LLM clients) is strongest in
Python. The frontend is a single-page application for local use. The initial research checked
current versions and wheel availability (see `docs/research/2026-11-initial-research.md`).

## Decision

**Backend**
- Python 3.13, managed with `uv`.
- FastAPI and Pydantic v2.
- SQLAlchemy 2.x (async) and Alembic.
- Jinja2 for prompt templates.
- Quality tools: ruff, mypy `--strict`, pytest and import-linter.

**Frontend**
- Node 24 LTS in containers.
- React 19, TypeScript, Vite 8, Tailwind CSS 4, shadcn/ui with Radix primitives, Lucide icons.
- TanStack Query for server state, TanStack Router, Zustand for the live-session store,
  react-hook-form and zod.
- Quality tools: Vitest, Testing Library, MSW and Playwright.

## Consequences

- Every native dependency checked (ctranslate2, onnxruntime, PyAV, piper-tts) has Python 3.13
  wheels for amd64 and arm64.
- shadcn now defaults to Base UI, so Radix must be selected explicitly (`-b radix`).
- Compatibility of TypeScript 7 with the lint and plugin tooling is to be verified when the
  frontend is bootstrapped; TypeScript 6.x is the fallback.

## Alternatives considered

- **Litestar** — capable, but with a smaller ecosystem than FastAPI.
- **A Node.js backend** — the speech and ML ecosystem is in Python.
- **Next.js** — server-side rendering brings nothing to a local single-page application.
- **SQLModel** — couples the API schemas, the ORM and the domain.
