# Processing tools and stated-limit reader

> **Historical checkpoint.** This records the state and checks at its original date. Later changes may supersede it.
> Current operational guides: [documentation index](../README.md), [architecture](../architecture.md), and [status](../status.md).

Date: 2026-11-10. This checkpoint extends the adaptive interview continuation note. It does not
close the independent model-quality acceptance gate.

## Implemented

- A `StatedLimitReader` port with independently selected LLM and ONNX implementations. The
  composition root chooses adapters. Domain and application import contracts exclude the
  infrastructure adapter, ONNX Runtime and tokenizers.
- Approved int8 model and tokenizer digests in `interview/infrastructure/limits_model.json`.
  Setup installs a preserved local export or an explicit HTTPS source, checks sizes and hashes,
  and publishes the directory only when verification succeeds. Backend models are read-only.
- Background loading, bounded CPU threads and disabled worker spinning. No PyTorch or weights
  are included in the backend image. The trained checkpoint and original weights remain outside
  Git; temporary training environments and the fp32 ONNX intermediate were removed separately.
- Four processing-tool menus in Settings, backed by fresh local-model checks, ChatGPT account
  status and classifier readiness. Only stated-limit reading offers Laya. The dashboard shows
  all four selections, and the preparation wizard no longer offers a provider choice.
- Versioned execution plans in the existing profile field, widened to text by migration 0007.
  Uniform legacy profiles remain valid. Plans survive storage and backups without external
  configuration lookups. Downgrades refuse mixed plans before altering either table.
- Tool changes and sign-out are blocked while interviews are connected or work is pending.
  Provider errors pause the interview and preserve answers. No provider fallback is configured;
  the selected provider must be restored before an explicit resume.

## Verification

- Full backend suite: 599 passed, 37 PostgreSQL cases skipped, 23 live cases deselected.
- After the final migration guard and CPU configuration changes: 83 storage and reader contract
  tests passed, covering both SQLite and a disposable PostgreSQL instance. The installed-model
  live reader check also passed. Ruff, strict mypy and all nine import contracts passed.
- Frontend lint, Feature-Sliced Design lint, type checking, formatting and production build
  passed; all 77 Vitest tests passed with two workers. A prior run under concurrent image builds
  timed out in an existing transcript-editor test; the final run passed without changing it.
- Browser suite: 17 passed, two opt-in full real-stack acceptance cases skipped. Settings,
  provider availability, the dashboard and preparation accessibility were checked. Screenshots
  of the real reader's settings were inspected on desktop and mobile.
- The API contract exported by the rebuilt runtime matches the checked-in contract. A live
  HTTP/WebSocket smoke check used real ONNX weights with scripted LLMs in an isolated application,
  including the in-call tool-selection guard and persisted classifier provenance.
- Reader benchmark: 261.5 ms median, 288.6 ms p90 for 40 reads at two CPU threads. This isolates
  the reader and is not an end-to-end measurement with a real interviewer.

The primary backend was recreated from the rebuilt image and is healthy. The prior tool defaults
were preserved; Laya is installed and available but is selected only through Settings. Temporary
test servers and the disposable database were stopped. No public model hosting or push was done.

## Remaining work

Independent stated-limit evaluation and real voice latency measurements remain open, as do the
broader adaptive-interview acceptance gates. Training/export scripts are preserved in the ignored
pilot directory; a versioned reproducible training/release pipeline and public model publication
remain separate work. The runtime integration does not require either to use the preserved model.
