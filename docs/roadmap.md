# Roadmap

Estimates are in **effective working days** for one person assisted by coding agents, review
included. The largest uncertainties are the quality of local models (prompts need iteration) and
browser audio behaviour.

## Ordering

The vertical slice comes first (M1–M3). It is followed by document analysis, the final UI,
evaluation and history. Three deliberate adjustments:

1. **Foundations and the text interview loop form a single milestone (M2).** It builds a minimal
   end-to-end path rather than horizontal plumbing with no consumer.
2. **Database persistence (M4) comes before document analysis**, which depends on it. Until then a
   deletable per-session file store is enough.
3. **Web and GitHub enrichment (M8) is split from CV and job-offer extraction (M5) and postponed.**
   The agentic crawler is the riskiest component and the least needed for the core loop.

```
M0 → M1 → M2 → M3 → M4 ─┬─► M5 ─┬─► M6
                        │       └─► M8
                        └─► M7 (needs M4; richer with M5) ─► M9          M10 later
```

**Priorities:**

| Priority | Milestones |
|---|---|
| P0 | M0–M3 (the vertical slice) |
| P1 | M4–M7 |
| P2 | M8–M9 |
| P3 | M10 |

## M0 — Repository bootstrap and design documentation · 0.5–1 day

- **Deliverables**
  - README, LICENSE (Apache-2.0), `.gitignore`, `.gitattributes`, `.editorconfig`, `AGENTS.md`.
  - The architecture document, the initial research and this roadmap.
  - ADRs 0001–0008.
  - A private GitHub repository.
- **Risks.** Committing personal data. Mitigated by a tested `.gitignore` and a docs-only
  repository.
- **Tests**
  - `git check-ignore` on sample paths, including the synthetic-fixture exception.
  - The remote's visibility is `PRIVATE`.
- **Done when**
  - the documents match the approved design;
  - the private remote exists;
  - no sensitive file is tracked.

## M1 — Technical spikes with predefined thresholds · at most 3 days (timeboxed)

- **Deliverables**
  - Throwaway scripts in `spikes/`, outside the package.
  - `docs/research/spike-results.md`.
  - ADRs 0009–0011 and default model profiles.
  - A minimal `compose.spike.yaml` (Ollama with GPU plus a Python container for the scripts).
  - A recommended `.wslconfig`.
- **Measurements**, all **inside containers**, with the native Ollama as a reference:
  0. **GPU in Docker Desktop.**
     - `nvidia-smi` inside a container.
     - The containerised Ollama runs 100% on the GPU.
     - Tokens per second compared with native Ollama, to quantify any WSL2 overhead.
  1. **LLM.** `qwen3.5:9b`, `ministral-3:8b`, `qwen3.5:4b` (and `gemma4:e4b` if time allows), with
     `think=false`:
     - time to first token and tokens per second with 2k, 4k and 8k prompts;
     - time to first token with an unchanged versus a modified prompt prefix;
     - cold-load time, and the reload cost when `num_ctx` changes;
     - CPU/GPU split in `ollama ps` **with Chrome open**.
  2. **Move format.**
     - "Header + text" versus constrained JSON: latency to the first sentence, and validity over 50
       moves.
     - Italian quality on 10 scripted turns, rated by hand with a simple grid.
  3. **Speech recognition on CPU, with Ollama loaded**, in a container limited to 6 and to 8 CPUs.
     - Engines: turbo int8, small int8, Parakeet.
     - Metrics: real-time factor, WER and tail latency after the click, on the test recordings.
     - Hallucinations on 2 minutes of silence.
     - WSL2 VM memory under load.
  4. **Speech synthesis.** Piper with paola, serena and riccardo: latency to the first audio per
     sentence, plus a comparative listening test.

**Pass/fail thresholds**, fixed in advance:

| Area | Threshold |
|---|---|
| LLM, warm model, 4k prompt | Time to first token ≤ 1.5 s |
| LLM, generation | ≥ 25 tokens/s |
| LLM, VRAM | No CPU offload at the chosen `num_ctx` |
| STT, turbo int8 on CPU | Real-time factor ≤ 0.5 |
| STT, accuracy | Italian WER ≤ 10% on the test recordings |
| STT, tail | Tail latency p50 ≤ 2 s |
| TTS | First audio of a 15-word sentence ≤ 600 ms |
| Move header | Valid in ≥ 95% of moves |

**If a threshold is missed**, the planned fallback is applied and documented:
- a 4B model for the interviewer;
- `small` or Parakeet for speech recognition;
- the JSON move format;
- native Ollama on the host, reached via `host.docker.internal`, if the GPU is unavailable in
  Docker Desktop.

- **Dependencies.** M0; consent for downloads and system configuration.
- **Risks.** No combination meets the thresholds. In that case the targets, or the use of a remote
  LLM, are discussed before M3.
- **Tests.** None; this is throwaway code.
- **Done when**
  - every combination has been measured;
  - every threshold has a pass/fail result;
  - the choices are recorded in the ADRs.

## M2 — End-to-end text skeleton · 7–10 days

- **Deliverables**
  - **Project setup**
    - The `backend/` project with `uv` and Python 3.13, using the initial layout from the
      architecture document (§7.1).
    - Settings, structured logging, `TrustedHostMiddleware`.
    - `docker/backend.Dockerfile`, multi-stage, non-root, with `dev` and `runtime` targets.
    - `compose.yaml` (backend and the `data` volume), `compose.nvidia.yaml` (Ollama with GPU) and
      `compose.dev.yaml` (watch).
  - **LLM access**
    - `ChatModel` with a native Ollama adapter and a fake.
    - A structured-output helper.
    - Versioned Jinja2 templates and a JSONL debug log.
  - **Interview core**
    - `interview` domain: session and state machine, `TimePolicy`, moves, header parser.
    - The LLM `Interviewer`.
    - An orchestrator with cancellation.
    - A text WebSocket protocol.
    - A file-based `SessionStore`.
    - YAML topics per interview type and a sample candidate brief.
  - **Tooling**
    - A development CLI client.
    - Interviewer evaluations with 3 scripted personas.
    - The import-linter rule for the domain.
    - Ubuntu CI: image build, then checks inside the container.
- **Dependencies.** M1.
- **Risks.** Interviewer quality; generalising too early. The port covers only what the
  orchestrator uses.
- **Tests**
  - The transition table.
  - `TimePolicy` with a fake clock.
  - `ScriptedInterviewer` scenarios: wrap-up, forced close, pause and resume, LLM error with the
    fallback phrase, cancellation at session end.
  - The header parser with malformed input.
  - `ChatModel` contract tests on the fake and on live Ollama.
  - The WebSocket protocol via `TestClient`.
  - Prompt snapshots.
- **Done when**
  - with a scripted candidate and a fake clock, a 15-minute interview ends **between 100% and
    115%** of the target duration, with a closing utterance;
  - with real Ollama on the 3 personas:
    - near-duplicate questions ≤ 5% (`rapidfuzz` ≥ 85);
    - 100% of turns in the configured language;
    - one question per turn in ≥ 90% of turns;
  - mypy `--strict` reports no errors, and CI is green;
  - on a clean clone, `docker compose -f compose.yaml -f compose.nvidia.yaml up` starts the skeleton
    with no host prerequisites other than Docker;
  - the backend answers only on `127.0.0.1`.

## M3 — Voice vertical slice · 10–14 days

- **Deliverables**
  - **Compose services**
    - `stt-worker` (CPU image; a CUDA variant only if M1 justifies it).
    - `tts-piper`: its own image with unmodified `piper-tts` and its HTTP server, with voices in the
      `models` volume.
    - Both have healthchecks and no published ports.
    - `frontend-dev` with Vite HMR in `compose.dev.yaml`. At runtime the backend serves the built
      SPA.
  - **Backend**
    - Speech ports with HTTP adapters (stt-worker, Piper) and fakes.
    - `TurnTranscriber`: VAD, incremental segments, a 15 s forced cut, anti-hallucination filters,
      finalisation.
    - `UtteranceSynthesizer`: streams sentence by sentence.
    - Binary audio in the WebSocket protocol, with frames outside the candidate's turn dropped.
    - `TurnMetrics`, and audio stored in the session directory.
  - **Frontend**
    - Bootstrap with Vite, React, TypeScript, Tailwind, shadcn (Radix) and TanStack.
    - A microphone check with a level meter.
    - A minimal meeting page: interviewer state, transcript, "answer", "end of answer", end call,
      timer.
    - AudioWorklet capture and a playback scheduler.
- **Dependencies.** M2.
- **Risks.** Browser and AudioWorklet quirks, latency, VRAM. That is why the estimate range is
  wider.
- **Tests**
  - `TurnTranscriber` on synthetic WAV files generated with Piper (no real voices).
  - The sentence splitter.
  - Resampling as a pure function (Vitest), and the session store.
  - **Playwright end-to-end** with Compose in the `test` profile (fake adapters) and a fake
    microphone fed from a WAV file, in CI.
  - The stt-worker's internal API contract: the same tests on the in-process adapter and on the
    HTTP one.
  - Deleting a session directory.
- **Done when**
  - a 10-minute Italian voice interview runs end to end on machine A with no manual intervention;
  - latency, **measured in the browser** from the "end of answer" click to the start of playback in
    the `AudioContext`, over at least 30 turns: **p50 ≤ 4 s and p95 ≤ 7 s**;
  - partial text appears within 3 s of a pause;
  - 2 minutes of silence produce no text;
  - end-to-end tests are green in CI;
  - deleting a session removes all of its files.

## M4 — Database persistence and transcript review · 5–7 days

- **Deliverables**
  - Async SQLAlchemy models, an Alembic baseline, repositories and a unit of work, a filesystem
    `BlobStore`.
  - An importer for file-based sessions, or their explicit discard.
  - Audio retention policies.
  - A session list.
  - A transcript editor with revisions and low-confidence words highlighted.
  - Re-transcription from the stored audio.
  - Cascading deletion.
  - PostgreSQL support.
- **Dependencies.** M3.
- **Risks.** SQLite/PostgreSQL differences, covered by contract tests on both.
- **Tests**
  - Repository contracts on SQLite and on PostgreSQL (Compose profile `postgres`, also in CI).
  - Migrations up and down.
  - Retention.
  - Deletion, files included.
- **Done when**
  - sessions survive a restart;
  - deletion removes rows and files (tested);
  - CI with PostgreSQL is green.

## M5 — Document analysis and context review · 8–12 days

- **Deliverables**
  - CV upload as PDF; job offer as PDF, text or URL (a single page via `UrlGuard`).
  - Text extraction in a process pool.
  - Section-by-section extraction with quote verification and invisible-text flagging.
  - `Fact` with origin and review status; the requirement matrix.
  - **The review UI.**
  - `ContextSnapshot` with its brief.
  - An LLM `Planner` fed by the snapshot.
  - Persisted `Activity`.
  - `JobRunner` with polling.
  - Extraction reuse by hash.
- **Dependencies.** M4.
- **Risks.** PDF layouts; extraction recall with a 9B model.
- **Tests**
  - `evals/` with at least 5 labelled synthetic CVs in Italian and English.
  - Quote verification, and a hidden-text fixture.
  - `UrlGuard`: private IPs, redirects, DNS rebinding, limits.
  - Snapshot immutability and hashing.
  - `JobRunner` recovery after a restart.
- **Done when**
  - at least 90% of extracted items have a verified quote;
  - **no item without a verified quote is shown as "Declared"**;
  - hidden text is flagged;
  - identical inputs reuse the snapshot;
  - the interviewer receives only non-excluded facts.

## M6 — Final UI · 6–10 days

- **Deliverables**
  - The Phase A wizard, polished review screens and the Phase D summary.
  - The final meeting room: the requested layout, a collapsible transcript, volume, states.
  - Settings: provider, model, voice, retention.
  - Model checks via `ModelCatalog`.
  - A diagnostics panel with `TurnMetrics` and `LlmInteraction`.
  - IT/EN i18n and basic accessibility.
- **Dependencies.** M5.
- **Risks.** Visual scope creep; the UI sticks to shadcn.
- **Tests.** Component tests, complete Playwright flows with fakes, axe checks.
- **Done when**
  - the A→E flow works without developer tools;
  - end-to-end tests are green;
  - axe reports no "serious" violations.

## M7 — Evaluation and reports · 8–12 days

- **Deliverables**
  - Rubrics v1 (HR, behavioral, technical, mixed) in YAML.
  - The evaluation pipeline.
  - Versioned reports and regeneration.
  - A report UI with citations that link to transcript turns.
  - An evaluator model profile and the disclaimer.
- **Dependencies.** M4; M5 for context.
- **Risks.** Shallow judgement from the local model; long run times.
- **Tests**
  - Validators and aggregation.
  - A fake LLM that **invents quotes**, which must be discarded.
  - Rubric versioning.
  - Regeneration creates v2 and keeps v1.
  - `evals/` with synthetic transcripts containing known technical errors, measuring the detection
    rate.
- **Done when**
  - **100% of displayed quotes are verified by code**;
  - every score has evidence or is `not_assessable`;
  - regeneration works;
  - the generation time on machine A is measured and documented.

## M8 — GitHub and web enrichment · 8–12 days

- **Deliverables**
  - A rate-limit-aware async `GitHubClient`, deterministic GitHub facts, README summaries with
    quotes.
  - A crawler built on `UrlGuard`, robots handling and trafilatura.
  - A budgeted agent with a single constrained tool.
  - Source statuses and injection signals.
  - Optionally, the fetcher as a separate egress-only service.
- **Dependencies.** M5.
- **Risks.** Prompt injection, site terms of use, rate limits.
- **Tests**
  - `respx` fixtures for GitHub.
  - A local server for robots, redirects to private IPs and limits.
  - A fake agent that tries links outside the allowlist, which must be refused.
  - Injection pages.
- **Done when**
  - every fact has a source;
  - no request leaves the allowlist (asserted at the transport level);
  - unavailable sources are shown with a reason.

## M9 — History and progress · 3–5 days

- **Deliverables**
  - History and comparisons, valid only when the rubric version is the same.
  - Per-criterion trends.
  - Markdown and JSON export, plus data export and backup.
  - "Delete all my data".
- **Dependencies.** M7.
- **Tests.** Queries, comparability rules, complete deletion.
- **Done when**
  - a trend appears with two or more comparable sessions;
  - non-comparable sessions are flagged.

## M10 — Live coding (future) · 15–25 days

Live coding needs a dedicated design document before it starts; see section 21 of the
architecture document.

## Totals

- **M0–M9:** about 60–85 effective days.
- **Vertical slice (M0–M3):** about 21–28 days.

## Open decisions

Only the decisions with an architectural or first-implementation impact are listed, each with a
default.

| # | Decision | Default | Closed by |
|---|---|---|---|
| 1 | Speech recognition engine and device | faster-whisper turbo int8 on CPU, incremental | M1 |
| 2 | Speech synthesis engine and Italian voice | Piper in its own container, paola or serena | M1 |
| 3 | Model and `num_ctx` | `qwen3.5:9b`, `think=false`, one `num_ctx` (8k) shared by every role using it | M1 |
| 4 | Interviewer move format | Header + text, with JSON as the fallback | M1 |
| 5 | Single user without authentication | Yes, published on `127.0.0.1` only | Approved with the design |
| 6 | Default audio retention | "Keep", with per-session and global deletion | M4 |
| 7 | Where Ollama runs on machine A | A Compose service with GPU (profile `nvidia`); native Ollama via `host.docker.internal` as the alternative | M1, together with the Docker Desktop GPU check |

## Operational prerequisites

Each prerequisite needs the owner's consent and is requested when it is needed.

- **Docker Desktop** running, with WSL2 integration and GPU support.
- **`.wslconfig` sizing.** Values are proposed after the M1 measurements.
- **Native Ollama** stopped while the containerised one runs.
- **Downloads for M1**
  - Base images: `ollama/ollama`, Python and Node.
  - Ollama models in the volume: `qwen3.5:9b` again (the volume cannot see the host's models),
    `ministral-3:8b` and `qwen3.5:4b`, plus `gemma4:e4b` optionally.
  - Whisper turbo and small, and Parakeet v3.
  - Piper voices.
- **STT test recordings.** 5–7 short Italian answers, read from a provided script, plus a few free
  answers. They stay in the data volume or in a git-ignored folder, and never enter the repository.
