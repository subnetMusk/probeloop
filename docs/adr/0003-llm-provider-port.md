# 0003 — Thin LLM port with a native Ollama adapter

> **Decision record.** Current implementation guidance is in [architecture](../architecture.md) and [configuration](../configuration.md); later ADRs amend specific decisions.

- Status: Accepted
- Date: 2026-11-03

## Context

Inference starts with local models through Ollama. A provider such as OpenAI may follow later.

Providers differ in several capabilities:

- streaming;
- structured output;
- tool calling;
- reasoning toggles;
- context window;
- acceptance of sampling parameters and system-role messages.

Ollama's OpenAI-compatible endpoints cannot set `num_ctx` per request, and the default context is
only 4096 tokens on GPUs with less than 24 GB. The native API also exposes `think`, `keep_alive`
and capability discovery (`/api/show`).

## Decision

Define a small `ChatModel` port with three operations:

- `capabilities()`;
- `complete(request)`;
- `stream(request)`.

Its data types:

- **`ChatRequest`** keeps instructions separate from messages. It carries an optional JSON Schema,
  a reasoning mode and an explicit context window.
- **`ModelCapabilities`** describes context window, streaming, structured output mode, tool
  calling, reasoning, vision, sampling parameters and system-role support.

Implementation:

- The first adapter uses the official `ollama` Python client against the native `/api/chat` API.
- Validation, repair retries and graceful degradation live in the application layer
  (`StructuredGenerator`), not in adapters.

## Consequences

- Full control over `num_ctx`, `think`, `keep_alive` and model capability discovery.
- Fakes are trivial, so orchestration is testable without a model.
- Agent loops, needed later for enrichment, have to be written by hand. A library such as
  pydantic-ai can be placed behind the port if that becomes worthwhile.

## Alternatives considered

- **LiteLLM** — heavy, and some versions were compromised on PyPI in 2026-03. No benefit with two
  providers.
- **pydantic-ai as the core** — it uses Ollama through `/v1`, losing per-request `num_ctx`, and it
  has a very fast release cadence.
- **instructor** — covers only structured output, which native `format` plus Pydantic already
  handles.
