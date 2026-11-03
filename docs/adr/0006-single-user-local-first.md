# 0006 — Single user, local-first

- Status: Accepted
- Date: 2026-11-03

## Context

ProbeLoop handles personal data (CVs, recordings, transcripts) for the person running it.
Multi-user operation is not a goal of the MVP. A later scenario uses a laptop with a remote LLM on
the local network.

## Decision

- The MVP is single-user and has no authentication.
- The backend is published only on `127.0.0.1`, with `TrustedHostMiddleware` (localhost only), a
  restrictive CORS policy, JSON content types on mutating requests and an `Origin` check on the
  WebSocket.
- LAN exposure is opt-in and requires both a token and HTTPS. Outside `localhost`, browsers allow
  microphone access only in a secure context.

## Consequences

- No user model, no accounts and no session management in the MVP.
- Exposing the application beyond localhost needs a dedicated milestone: authentication, TLS
  through a reverse proxy, and a review of the threat model.

## Alternatives considered

- **Authentication from day one** — cost without benefit for a localhost-only tool.
