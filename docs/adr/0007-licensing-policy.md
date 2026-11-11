# 0007 — Licensing policy

> **Decision record.** Current implementation guidance is in [architecture](../architecture.md) and [configuration](../configuration.md); later ADRs amend specific decisions.

- Status: Accepted
- Date: 2026-11-03
- Amended: 2026-11-11, installer notices and separate model publication.

## Context

The project is open source. Several attractive components carry copyleft licenses:

- PyMuPDF and pymupdf4llm are AGPL.
- The Piper TTS engine is GPL-3.0-or-later, and so is espeak-ng.

Model weights and voices have their own licenses, for example CC-BY-4.0 for Parakeet and
CC0, CC-BY-4.0 or M-AILABS for the Piper voices.

## Decision

- ProbeLoop is licensed under **Apache-2.0**.
- No AGPL library is used.
- GPL components are never imported in-process. They run only as separate, unmodified programs in
  their own containers, reached over HTTP; Piper runs as the `tts-piper` service.
- Runtime images and installer archives contain no model weights or voices. Users download
  approved models separately; the provisional Laya fine-tuning is published separately on
  Hugging Face. Documentation and UI show their own licences and attribution.
- Any third-party code that is copied keeps its notice in `THIRD_PARTY_NOTICES.md`.
- `LICENSE`, `NOTICE` and third-party attributions accompany the installer and images.
  Frontend bundles preserve production-package notices; full font licences accompany the assets.

## Consequences

- PDF parsing uses permissively licensed libraries (pypdf or pdfplumber).
- Italian TTS, whose good options all involve GPL components, requires a separate service.

## Alternatives considered

- **AGPL-3.0 for ProbeLoop** — would allow GPL components in-process, but reduces adoption.
- **MIT** — no explicit patent grant.
