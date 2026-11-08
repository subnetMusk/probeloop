# Roadmap

Estimates are in **effective working days** for one person assisted by coding agents, review
included. The largest uncertainties are the quality of local models (prompts need iteration) and
browser audio behaviour.

## Ordering

The vertical slice comes first (M1–M3). The approved order is persistence, document analysis,
CV review, interview evaluation, UI polish and history:

1. **Foundations and the text interview loop form a single milestone (M2).** It builds a minimal
   end-to-end path rather than horizontal plumbing with no consumer.
2. **Database persistence (M4) comes before document analysis**, which depends on it. Until then a
   deletable per-session file store is enough.
3. **M8 is dropped.** Documents and titled resources are supplied by the user; links are never
   followed. The decisions in [the context proposal](proposals/2026-11-context-evaluation-reports.md#9-decisions)
   supersede the earlier web-enrichment design.

```
M0 → M1 → M2 → M3 → M4 → M5 → CV review → M7 → M6 → M9       M10 later
```

**Priorities:**

| Priority | Milestones |
|---|---|
| P0 | M0–M3 (the vertical slice) |
| P1 | M4–M7 |
| P2 | M9 |
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

> **Status (2026-11-06): measurements done, two items pending.** The results are in
> [research/spike-results.md](research/spike-results.md), and ADRs 0009–0011 record the decisions.
> Still pending:
> - WER on real recordings (the spike so far used synthetic speech);
> - the listening test for the default Piper voice.

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

> **Status (2026-11-06): implemented, pending CI on GitHub.**
>
> **Local checks** (inside the dev container): ruff, mypy `--strict`, import-linter, 105 tests,
> and live contract tests against `ministral-3:8b`.
>
> **Persona evaluation** (`evals/interviewer_personas.py`, three personas, simulated 15-minute
> interviews):
> - near-duplicate questions 0%;
> - Italian 100%;
> - one question per turn 100%;
> - length 100–110% of the target;
> - no fallbacks.
>
> **History of the one-question result.**
> - Prompt v1: 18–73% of turns had a single question.
> - Prompt v2: 18–100%.
> - The remaining sub-questions are now cut in code (architecture §10.2).
> - The evaluation also counts a single formal request without a question mark ("Mi descriva...")
>   as one question, and reports the strict question-mark count next to it.
>
> **Runtime check.** `docker compose up` publishes on `127.0.0.1` only, with a read-only
> filesystem, and a CLI interview runs end to end.
>
> **Known model behaviours left for the M7 evaluator work:**
> - occasional invented details in the closing ("La ricontatteremo entro una settimana");
> - occasional repeated insistence when the candidate does not answer.

- **Deliverables**
  - **Project setup**
    - The `backend/` project with `uv` and Python 3.13, using the initial layout from the
      architecture document (§7.1).
    - Settings, structured logging, `TrustedHostMiddleware`.
    - `docker/backend.Dockerfile`, multi-stage, non-root, with `dev` and `runtime` targets.
    - `compose.yaml` (backend and the `data` volume; `OLLAMA_BASE_URL` defaults to the host's
      native Ollama), `compose.nvidia.yaml` (optional Ollama service with GPU, for Linux hosts)
      and `compose.dev.yaml` (watch).
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
  - on a clean clone, `docker compose up` starts the skeleton with no host prerequisites other
    than Docker and the native Ollama;
  - the backend answers only on `127.0.0.1`.

## M3 — Voice vertical slice · 10–14 days

> **Status (2026-11-07): implemented; the criteria that need a real voice are pending.**
>
> **Built:** the deliverables below, plus what the first runs asked for:
> - starting an interview loads the model, the recogniser and the voice, with progress on screen;
> - only one interview can be active at a time;
> - a finished interview leaves `transcript.json`, `transcript.md` and `audio/interview.wav`;
> - a synthetic voice candidate (`evals/voice_candidate.py`) for end-to-end runs.
>
> **Checks:** 321 backend and 22 frontend unit tests, live contract tests of both speech engines,
> and the Playwright end-to-end test in CI.
>
> **Measured with the synthetic voice candidate** (technical interview, 10 minutes, 16 answers
> written live by an agent and spoken by Piper):
> - mean WER 7.8% (max 21%) on synthetic speech;
> - reply latency (end of answer to the first audio of the reply, at the client) p50 3.5 s,
>   p95 4.7 s, max 5.9 s. One-sentence questions waited for the whole sentence before synthesis;
>   the first chunk is now cut at a clause, not yet re-measured;
> - one turn measured in the browser: 2.0 s.
>
> **Pending, with the repository owner:**
> - a 10-minute interview with a real voice;
> - latency over at least 30 turns measured in the browser;
> - WER on real recordings and the default voice (deferred).
>
> **Observed, for later milestones:**
> - Parakeet garbles English technical terms ("FastAPI" became "FastaP", "cache" became
>   "caca"), partly because Piper mispronounces them in synthetic answers. The post-interview
>   Whisper pass with a vocabulary prompt fixes part of it (16% to 7% WER on one fixture).
> - The interviewer sometimes asks to clarify a misrecognised term, rarely probes a gap the
>   candidate admits, addresses the candidate by name in almost every turn, and can add invented
>   details to the farewell.

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

> **Status (2026-11-08): implemented and verified locally.**
>
> Documents, reusable resource profiles, asynchronous analysis, review and immutable snapshots
> are connected to the interview planner and Whisper vocabulary. A quick start without documents
> remains available. Generated offers are labelled in the API and UI; the area must be confirmed
> before approving a preparation without an offer.
>
> **Live extraction evaluation:** `qwen3.5:9b`, five labelled synthetic CVs (three Italian,
> two English), 52/52 facts with verified quotes (100%, target ≥90%), 29/30 labelled facts
> recovered with their identifying details (96.7%), hidden text detected and excluded. Evidence
> span coverage alone was 30/30; it is reported separately from fact recall. See
> [the measurements and limitations](research/context-extraction-results.md).
>
> **Checks:** 388 backend tests, 22 PostgreSQL contracts, 25 frontend tests and four Playwright
> flows, plus ruff, mypy, seven import contracts, ESLint, TypeScript, formatting and builds.
> Generated contracts are reproducible. The rebuilt runtime completed document analysis with
> the real model and produced an approved snapshot; the real speech services report ready.

- **Deliverables**
  - CV and job offer as files or pasted text; editable generated offers from a role description.
  - Titled text/file resources in reusable profiles, with overwrite / save new / use once choices.
  - Text extraction in a process pool.
  - Section-by-section extraction with quote verification and invisible-text flagging.
  - `Fact` with origin and review status; the requirement matrix.
  - **The review UI.**
  - `ContextSnapshot` with its brief.
  - An LLM `Planner` fed by the snapshot.
  - The existing persisted session and turns remain the single conversation activity.
  - `JobRunner` with polling.
  - Extraction reuse by hash.
- **Dependencies.** M4.
- **Risks.** PDF layouts; extraction recall with a 9B model.
- **Tests**
  - `evals/` with at least 5 labelled synthetic CVs in Italian and English.
  - Quote verification, and a hidden-text fixture.
  - No URL input or network fetching; HTML/XML resources are reduced to text.
  - Snapshot immutability and hashing.
  - `JobRunner` recovery after a restart.
- **Done when**
  - at least 90% of extracted items have a verified quote;
  - **no item without a verified quote is shown as "Declared"**;
  - hidden text is flagged;
  - identical inputs reuse the snapshot;
  - the interviewer receives only non-excluded facts.

## CV review — after M5, before M7

The approved scope is [proposal section 3](proposals/2026-11-context-evaluation-reports.md#3-cv-review-new):
versioned rubric YAML, deterministic checks, evidence-verified model judgements, a background job
and a report page. The [CV rating requirements](proposals/2026-11-cv-rating-guidelines.md) incorporate
the owner's general guidelines, evidence limits and draft anchors for calibration.

**Status (2026-11-08): implemented and verified locally.** Reviews run as persisted jobs,
retain immutable versions and expose verified quotations, deterministic diagnostics and explicit
not-assessable checks. The report language follows the application preference; practice questions
feed the interview planner as suggestions. Model work is serialised and waits during a live call.

The synthetic CV smoke run on `qwen3.5:9b` with thinking took **91.82 seconds**, with seven
assessable criteria and no rejected quotations. It detected the reversed date range and requested
more decision/scope detail. A preceding run exposed an unsupported claim about an unvisited link;
URL-only evidence is now rejected. This is a smoke measurement, not full calibration. See
[the evaluation notes](research/cv-review-results.md).

Validation: 401 backend tests, 23 targeted assessment/storage/job checks including PostgreSQL,
26 frontend tests, four browser flows (the voice flow rerun separately after allowing for final
recording persistence), strict typing, linting, nine dependency contracts and rebuilt artifacts.

## M6 — Final UI · 6–10 days

**Checkpoint (2026-11-08), not complete:** language, volume, theme, report notifications and
IT/EN scaffolding are implemented. Remaining translation, final rebuilt-app/E2E checks and
accessibility acceptance are recorded in the [continuation notes](handoffs/2026-11-08-assessment-continuation.md).
The implemented settings currently cover proposal section 7, not every older configuration and
diagnostics deliverable below. The provider choice is the execution profile (local, or the
ChatGPT plan through Sign in with ChatGPT, [ADR 0013](adr/0013-cloud-execution-profile.md));
models are chosen in the environment, not in the UI.

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

**Checkpoint (2026-11-08), not complete:** rubrics, two-pass unit scoring, evidence verification,
versioned reports, delivery metrics, report UI and exports are implemented. The first real-model
smoke took 1,646 seconds for three graded units and produced a technical false positive. The
revised pipeline ([ADR 0012](adr/0012-interview-evaluation-pipeline.md)) judges without
thinking through an evidence-first schema, keeps both anchor orders, checks reported corrections
independently and synthesises by reference. On the same labelled transcript it took about 120 s
per report and passed the labelled checks; see the
[latency note](research/evaluation-latency.md). The first persona calibration
([results](research/interview-calibration.md)) ranked every strong answer above its weak pair with
no unverified quotation, but missed the detection and spread thresholds: the past-example
classification was unreliable (fixed in classification v3, calibration not yet rerun) and vague
ownership is not detected. The ownership decision, a calibration rerun and the two voice
acceptance interviews remain open, see the
[continuation notes](handoffs/2026-11-08-assessment-continuation.md).

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

## M8 — GitHub and web enrichment

**Dropped by the approved context proposal.** Resources are uploaded or typed by the user.
No crawler, GitHub client, enrichment job or URL fetcher is planned.

## M9 — History and progress · 3–5 days

**Checkpoint (2026-11-08), not complete:** latest-version progress groups, portable backups,
empty-target restore and delete-all are implemented. Targeted SQLite/PostgreSQL checks passed;
complete browser integration, error-path review and documentation remain open. See the
[continuation notes](handoffs/2026-11-08-assessment-continuation.md).

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
| 1 | Speech recognition engine and device | **Closed (ADR 0009):** Parakeet on CPU for live transcription, Whisper turbo refinement after the interview. To be confirmed on real recordings. | M1 |
| 2 | Speech synthesis engine and Italian voice | **Engine closed (ADR 0010):** Piper in its own container. Voice: serena-medium or paola-medium, pending the listening test. | M1 |
| 3 | Interviewer model and `num_ctx` | **Proposed (M1):** `ministral-3:8b` at 8k, with `qwen3.5:9b` as the alternative and evaluator candidate. 16k causes CPU offload on 8 GB. | Confirmed in M2 with the interviewer evaluations |
| 4 | Interviewer move format | **Closed (ADR 0011):** constrained JSON, 100% valid, parsed incrementally | M1 |
| 5 | Single user without authentication | Yes, published on `127.0.0.1` only | Approved with the design |
| 6 | Default audio retention | "Keep", with per-session and global deletion | M4 |
| 7 | Where Ollama runs on machine A | **Closed (M1):** the native Ollama on the host via `host.docker.internal`. The containerised Ollama loaded models 3–15× slower. | M1 |

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
