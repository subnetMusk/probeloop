# 0004 — Persistence

> **Decision record.** Current implementation guidance is in [architecture](../architecture.md) and [configuration](../configuration.md); later ADRs amend specific decisions.

- Status: Accepted
- Date: 2026-11-03

## Context

The application stores configurations, context snapshots, transcripts with revisions, audio,
reports and metrics. It is single-user and self-hosted, and runs under Docker Compose (ADR 0008).
SQLite should be the default and PostgreSQL a supported alternative. The realtime path (WebSocket,
LLM streaming) is fully asynchronous.

## Decision

**Until milestone M4**
- A file-based session store keeps one directory per session in the `data` volume, holding a JSON
  document and the audio files.
- Deleting a session removes its directory.

**From M4**
- SQLite by default, with WAL and foreign keys enabled. PostgreSQL is available through a Compose
  profile.
- SQLAlchemy 2.x in async mode (aiosqlite / asyncpg), and Alembic with batch mode for SQLite.
- ORM models are separate from domain entities, with explicit mapping inside the repositories.
- Ids are UUIDv7. JSON columns hold flexible payloads.
- Blobs (documents and audio) live on the filesystem in the `data` named volume. Documents are
  content-addressed by sha256.
- PostgreSQL contract tests run in CI from M4 on, to prevent SQLite-only constructs.

## Consequences

- No database is needed for the vertical slice, and personal data stays deletable from day one.
- Named volumes avoid slow NTFS bind mounts and SQLite locking problems on Docker Desktop for
  Windows.
- Mapping code between ORM models and entities must be maintained.

## Alternatives considered

- **Imperative mapping onto domain entities** — brings ORM instrumentation and lazy-loading
  behaviour into the domain.
- **Synchronous SQLAlchemy in a thread pool** — mixes models in an otherwise async codebase.
- **PostgreSQL as the default** — heavier for a single-user local tool.
