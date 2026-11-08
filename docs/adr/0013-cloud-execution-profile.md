# 0013 — Optional cloud execution profile through an OpenAI-compatible adapter

- Status: Accepted
- Date: 2026-11-08

## Context

ProbeLoop is local-first ([ADR 0006](0006-single-user-local-first.md)). On machine A the
interviewer runs on `ministral-3:8b`, and analysis and evaluation run on `qwen3.5:9b`. Small
local models limit the quality of the interviewer and the reports:

- they did not follow several evaluation rules ([ADR 0012](0012-interview-evaluation-pipeline.md));
- they carry technical misconceptions into advice.

The owner asked for a second way to run the language models: a cloud model used as an API,
selectable from the UI. Speech recognition and synthesis stay local in both cases. That covers
the live recogniser, the refinement pass after the call and Piper.

[ADR 0003](0003-llm-provider-port.md) prepared for this. Its `ChatModel` port keeps instructions
apart from messages and describes provider capabilities. The prompts were kept provider-neutral
so that a stronger model is not biased by wording written for a small one.

Facts from OpenAI's documentation, read on 2026-11-08:

- **Models.** The latest-model guide lists `gpt-6-astra`, `gpt-6.1-sol`, `gpt-6.1-terra` and
  `gpt-6-luna`.
- **Reasoning effort.** `gpt-6.1-terra` accepts the reasoning effort `none`; `gpt-6.1-sol` and
  `gpt-6-astra` do not.
- **Sampling.** `temperature` and `top_p` must be removed whenever the reasoning effort is not
  `none`.
- **Output cap.** `max_completion_tokens` includes reasoning tokens.
- **Strict structured outputs.** They require every property to be listed as required and
  `additionalProperties: false` on every object.
- **Usage.** Chat Completions streams report token usage in a final chunk when
  `stream_options.include_usage` is set.

## Decision

**Adapter.** `OpenAIChatModel` implements the port over the Chat Completions API, using plain
`httpx` and a configurable base URL, so the same adapter serves OpenAI and compatible servers.

- **Structured output.** Response schemas are sent as strict JSON schemas. The adapter makes
  every property required and forbids extra properties. If the provider rejects a schema as
  outside the strict subset, the adapter continues once and for all in best-effort mode. The
  application layer validates every output anyway.
- **Reasoning and sampling.** A request with reasoning off sends the configured reasoning effort:
  `none` by default, `low` for models without `none`, or nothing for models without reasoning
  control. Temperature, `top_p`, a non-zero presence penalty and the output cap are sent only
  when no reasoning tokens are generated.
- **Resilience.** Rate limits, server errors and connection failures are retried twice with
  backoff. A context overflow raises `ContextOverflowError`, and a refusal raises `LlmError`.
  Error messages never include prompt text or the key.

**Execution profiles.**

- **Two profiles.** *local* (the default) and *cloud*.
- **What the profile covers.** It applies to three roles: the interviewer, including topic
  planning; document analysis; and evaluation, which means CV review and interview reports.
  Each role routes every call to the model of the profile selected when the call starts.
- **Where the choice is made.** The profile is chosen in Settings and stored in
  `execution-profile.json` in the data directory. It is configuration, not user data: backups,
  restores and "delete all my data" do not touch it.
- **When it can change.** The profile changes only when no interview is connected and no job is
  queued or running, so no interview or report mixes models.
- **Default cloud models.** `gpt-6.1-terra` for all three roles, with reasoning effort `none`.
  Every model, the base URL and the reasoning setting are environment variables.

**Credentials.** The API key is read only from `PROBELOOP_CLOUD_API_KEY`, through `.env` and
Compose. Without a key the cloud profile is shown as not configured. The UI never asks for the
key, and the key is never stored in the database, logs or backups.

**Consent.** Selecting the cloud profile asks for confirmation and states what leaves the
machine. While the profile is active, the Settings page shows a notice.

## Consequences

- With the cloud profile, CVs, documents, transcripts and answers are sent to the provider
  under the provider's API data terms. Audio never leaves the machine.
- Reports record the cloud model in their provenance. Progress groups already require the same
  model, so cloud and local reports are never compared.
- The interviewer's latency now depends on the network and the provider. Background jobs still
  wait for live interviews, as they do for the single local GPU, although the cloud profile does
  not need that.
- The adapter is verified against scripted HTTP streams in unit and contract tests. A live
  contract run (`pytest -m live`, billed) and a cloud run of the evaluation comparison set still
  need an API key. The default model IDs come from the guide and may need updating.
- Follow-up: compare the cloud and local profiles on the labelled transcript and the persona
  calibration set before relying on cloud reports.

## Alternatives considered

- **The official `openai` SDK** — one more dependency for a single endpoint. Plain HTTP also keeps
  the adapter usable with other compatible servers.
- **The Responses API** — OpenAI's recommended interface, and the only one with GPT-6 tool calling.
  ProbeLoop uses no tools, and Chat Completions is the interface that compatible servers share.
- **"Sign in with ChatGPT"** — a preview at research time ([initial research, section 7](../research/2026-11-initial-research.md)),
  with these limits: no system role, no sampling parameters or output cap, and undocumented
  structured outputs. The owner asked for API use.
- **Entering the key in the UI** — the backend would have to store a secret in the database or
  the data directory, where backups would pick it up.
- **Choosing the provider per role in the UI** — more combinations to test and explain; the
  environment variables already allow per-role models within the cloud profile.
