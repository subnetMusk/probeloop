# 0001 — Modular monolith with pragmatic hexagonal architecture

- Status: Accepted
- Date: 2026-11-03

## Context

ProbeLoop must be able to swap LLM providers, speech engines and storage backends, and keep the
domain free of framework, database and AI-vendor dependencies. It is a single-user, self-hosted
application developed by a small team with the help of coding agents. Testability and
reviewability matter more than independent scalability.

## Decision

Build a modular monolith using ports and adapters.

- **Business modules.** `interview`, `context`, `assessment` and `speech`. Each separates
  `domain`, `application` (use cases and ports), `infrastructure` (outbound adapters) and `api`
  (presentation).
- **Dependencies point towards the domain.** Only the composition root (`bootstrap`) knows
  concrete adapters.
- **Ports exist only where variability is real**: providers, engines and storage.
- **A module is created when it gets its first real consumer.**
- **import-linter enforces the rules.** It starts with one rule: the domain imports no framework,
  ORM, Pydantic, vendor SDK or adapter. Further rules are added when the modules exist.

## Consequences

- The domain and the orchestration logic can be tested with fakes in milliseconds.
- Providers and engines can be replaced without touching the domain.
- Some mapping code is needed between domain entities, ORM models and API schemas.
- Discipline is required to avoid speculative interfaces. The architecture document lists which
  abstractions are introduced at which milestone.

## Alternatives considered

- **Microservices** — operational cost without benefit for a single-user application.
- **Layered architecture without ports** — provider and engine coupling would leak into use cases.
- **Strict DDD with event sourcing** — unjustified complexity at this stage.
