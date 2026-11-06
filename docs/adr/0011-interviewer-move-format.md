# 0011 — Interviewer move format: constrained JSON

- Status: Accepted
- Date: 2026-11-06

## Context

Each interviewer turn is one streamed LLM call that must deliver a machine-readable decision
(`action`, `topic_id`, covered topics) and the utterance, whose first sentence should reach TTS as
early as possible. The design compared two formats:

- constrained JSON (Ollama `format` with a JSON Schema);
- a plain-text "header + text" format, with the decision on the first line and the utterance
  after it.

M1 measured three models (qwen3.5:9b, ministral-3:8b, qwen3.5:4b), with 20–50 moves per format
over ten scripted interview states:

| | Constrained JSON | Header + text |
|---|---|---|
| Valid moves | 100% | 76–95% |
| First complete sentence of the utterance, p50 | 0.80–0.99 s | 0.67–1.02 s |

Under constrained JSON the schema's property order was respected in 90 of 90 moves.

## Decision

Use constrained JSON with this property order:

```json
{"action": "...", "topic_id": "...", "utterance": "...", "covered_topic_ids": ["..."]}
```

- The stream is parsed incrementally (`pydantic_core.from_json(..., allow_partial="trailing-strings")`).
  Each completed sentence of `utterance` is sent to TTS.
- No reasoning field precedes the utterance, and reasoning mode is off.
- The adapter must keep a test asserting that the property order is preserved, because the
  latency depends on it.

## Consequences

- The interviewer move is always machine-readable, so no fallback parsing or default action is
  needed.
- **The format guarantees structure, not good decisions.** Semantic quality must still be covered
  by the interviewer evaluations. M1 recorded several quirks:
  - `new_topic` chosen after a vague answer;
  - an occasional implausible `present_exercise` in the opening;
  - two questions in one turn.
- The same structured-output path serves the realtime and the batch uses.

## Alternatives considered

- **Header + text** — lower validity, and no latency advantage in practice.
- **Two calls (a decision, then the utterance)** — adds a round trip and breaks the single-call
  KV-cache reuse.
