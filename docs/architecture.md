# ProbeLoop architecture

- **Status:** initial design, approved before implementation. Sections marked *to be measured*
  depend on the technical spikes of milestone M1.
- **Date:** 2026-11-03.
- **Related:** [roadmap](roadmap.md), [initial research](research/2026-11-initial-research.md),
  [ADRs](adr/).

**Context and assessment update (2026-11-07).** The approved
[context proposal](proposals/2026-11-context-evaluation-reports.md#9-decisions) supersedes the
original web-enrichment, context-input and rubric plans below. M8 is dropped: CVs, offers and
titled resources are uploaded or typed; links are never followed. Resources are reused through
profiles. M5 implements this revised context flow; CV review precedes M7 and UI polish follows it.

## 1. Purpose

ProbeLoop is a self-hosted platform for spoken mock job interviews with an AI interviewer. The
user moves through seven phases:

1. **Preparation.** Upload or paste a CV, an optional job offer and titled resources, then choose the interview type,
   difficulty, duration, language, model and custom instructions.
2. **Analysis.** The system extracts structured information with verified quotes and matches it
   against the job requirements, or infers an area that the user confirms without an offer.
3. **Human review.** Every fact is shown with its provenance and epistemic status. The user
   confirms, corrects or excludes it. The approved result is frozen into an immutable context
   snapshot.
4. **Summary and start.**
5. **Spoken interview with explicit turn-taking.** Text-to-speech plays the question, the
   candidate answers, speech recognition transcribes progressively, the candidate presses
   "end of answer", and the interviewer decides the next move.
6. **Transcript review and evaluation.** The evaluator is separate from the interviewer. It
   applies versioned rubrics, cites evidence for every judgement, and its reports can be
   regenerated.
7. **History and progress tracking.**

The value lies in three things: the quality of the conversation, the fidelity of the
transcription, and the honesty of the feedback. Avatars and video are explicitly out of scope.

The cross-cutting engineering goal is that **every statement produced by the system is
traceable to a source**:

- a fact to its evidence;
- a judgement to a transcript quote;
- a score to the rubric and rubric version that produced it.

### Problems this design addresses

The project grew out of experience with an existing university mock-interview tool, which
showed four problems:

| Problem | Countermeasures |
|---|---|
| Transcription errors leaking into the evaluation | Vocabulary-biased incremental STT, confidence highlighting, user correction, re-transcription, ASR-aware evaluator |
| Answers evaluated in isolation | Segment-level evaluation with the surrounding exchange and a global summary |
| Suggestions that introduce facts the candidate never stated | Deterministic quote verification; hypothetical examples labelled as such |
| Little control over interviewer behaviour and criteria | Configurable interview types, versioned rubrics, bounded custom instructions |

## 2. Defaults for open points

| Topic | Default |
|---|---|
| Users | Single user, local-first. The backend is published on `127.0.0.1` only, with no authentication in the MVP. LAN exposure comes later, opt-in, with a token and HTTPS. |
| macOS scenario | The same Compose stack runs on the Mac (arm64 images) without the Ollama service. The LLM runs remotely: Ollama on the PC over the LAN, or a future provider. Docker on macOS has no Metal access, so speech recognition runs on the CPU in the container, or as a native MLX worker on the host reached over HTTP. |
| Interview language | Italian and English from the start. System prompts are in English and the output language is a parameter (*to be measured*). The UI starts in English, with IT/EN i18n added in M6. |
| Fact status | Two independent axes: **origin** (CV statement, user entry, external source, model inference) and **review** (pending, confirmed, corrected, excluded). Quote verification is an attribute of the evidence. |
| Progressive transcript | Partial text is shown while the candidate speaks. The explicit end-of-turn action finalises it. The final transcript is authoritative and can be corrected after the call. |
| Interview plan visibility | Hidden during the interview. Visible in the report and in diagnostics mode. |
| Custom instructions | Affect only the interviewer's style and focus. The evaluator never receives the free text, only structured focus areas. |
| Audio retention | A per-session policy (keep / delete after report / do not store), with a global default. "Keep" enables re-transcription. |
| Report regeneration | Always creates a new report version, linked to the transcript revision it used. Old versions remain available. |

## 3. Implicit constraints

- **Personal data.** CVs, transcripts and audio stay in local Docker volumes. They never enter the
  repository, the images or INFO-level logs. Complete deletion is a first-class feature.
- **Small local models (~9B parameters).**
  - JSON reliability and judgement quality are limited. The system compensates with constraints,
    validation and task decomposition.
  - A different model can be configured for each role (interviewer, extractor, evaluator).
  - Evaluation is a batch job, so it may use a larger, slower model.
- **VRAM contention.** The 8 GB of the development GPU is the dominant hardware constraint. By
  default the GPU is reserved for the LLM.
- **Conversational latency** is split into measurable stages:
  - speech-recognition finalisation;
  - time to the LLM's first token;
  - time to the first audio chunk.

  Reasoning ("thinking") mode is disabled for the interviewer.
- **Untrusted content.** CVs, web pages, READMEs and custom instructions are all prompt-injection
  vectors. A known real-world example is hidden white-on-white text in a CV inflating a screening
  score. The defences are least privilege and human review.
- **Reproducibility.** Every AI artifact records the model, prompt version, rubric version and
  inputs it used.
- **Licensing.**
  - The project is Apache-2.0, so AGPL libraries are not used in-process.
  - GPL tools run as separate programs.
  - Model weights and voices are downloaded by the user and keep their own licenses, which the UI
    and documentation show.

## 4. Main architectural risks

| Risk | Impact | Mitigation |
|---|---|---|
| LLM and speech recognition do not fit together in 8 GB of VRAM | High latency or CPU offload | M1 measurements; speech recognition on CPU; explicit `num_ctx` |
| End-of-turn latency too high (> 5–6 s) | Unnatural conversation | Interviewer move streamed as constrained JSON with the utterance parsed incrementally; per-sentence TTS; incremental STT; append-only prompt layout for KV-cache reuse (measured in M1: 0.6–0.9 s to the first token with the cache, 3.5–4.7 s without) |
| Judgement quality of a 9B model in Italian | Shallow or wrong reports | Segment-level evaluation, verified quotes, score aggregation in code, configurable evaluator model |
| Hallucinations in extraction and reports | Invented facts | Every item carries a source quote verified by fuzzy matching; unverified items are downgraded or discarded |
| Prompt injection from documents | Manipulated behaviour or scores | Content handled as data, no dangerous tools, human review, evaluator isolated from raw external content |
| Docker Desktop on Windows: GPU via WSL2, file watching on NTFS bind mounts, SQLite on bind mounts, WSL2 RAM | No GPU, slow reload, database locking, swapping | GPU check in M1; `docker compose watch` (file sync) for code; data on named volumes; `.wslconfig` sized in M1 |
| Overengineering through hexagonal layering | Slow progress, noise | Ports only where variability is real; modules created with their first consumer |
| Frontend/backend contract drift | Integration bugs | TypeScript types generated from OpenAPI and from the JSON Schema of WebSocket messages; drift check in CI |

## 5. Components

```
┌─────────────────────────────── Browser: React SPA ────────────────────────────────┐
│ Setup wizard │ Context review │ Meeting room │ Transcript editor │ Report │ History │
│ TanStack Query (REST)     AudioWorklet mic → PCM16 16 kHz ─┐   ┌─ TTS player       │
└──────────────┬─────────────────────────────────────────────┼───┼───────────────────┘
        REST/JSON (OpenAPI)                     WebSocket /ws/sessions/{id} (JSON + binary)
┌──────────────┴─────────────────────────────────────────────┴───┴───────────────────┐
│ FastAPI — presentation: routers per module, WS gateway, static SPA                 │
├────────────────────────────────────────────────────────────────────────────────────┤
│ Application: use cases per module + shared services                                │
│  context: ingest · extract · enrich · review · snapshot                            │
│  interview: SessionOrchestrator · Interviewer (LLM) · Planner · ConversationMemory │
│  assessment: EvaluationPipeline · ReportService                                    │
│  speech: TurnTranscriber (incremental) · UtteranceSynthesizer (per sentence)       │
│  ai: StructuredGenerator · PromptRenderer · ContextGuard   platform: JobRunner      │
├────────────────────────────────────────────────────────────────────────────────────┤
│ Domain (pure Python): Session + state machine, Activity, Turn, TranscriptRevision, │
│  Fact/Evidence, ContextSnapshot, Rubric, Report, TimePolicy, EvidencePolicy        │
├────────────────────────────────────────────────────────────────────────────────────┤
│ Ports (typing.Protocol) ← Adapters (infrastructure)                                │
│  ChatModel/ModelCatalog → Ollama | ChatGPT plan   | Fake                           │
│  SpeechToText → HTTP → stt-worker (faster-whisper CPU|CUDA, Parakeet) | Fake      │
│  TextToSpeech → Piper (separate process, HTTP) | browser Web Speech (later) | Fake │
│  DocumentTextExtractor → pypdf/pdfplumber in a process pool                        │
│  WebFetcher, GitHubClient → httpx + UrlGuard (SSRF, robots, limits) | Fake         │
│  Repositories + UnitOfWork → SQLAlchemy (SQLite | PostgreSQL) | in-memory          │
│  BlobStore → local filesystem | S3 (later)                                         │
│  CodeRunner (future) → sandboxed container                                         │
└────────────────────────────────────────────────────────────────────────────────────┘
   External: Ollama (compose service or LAN) · model caches (Hugging Face, voices) in volumes
```

## 6. Deployment with Docker Compose

```
host (Windows: Docker Desktop + WSL2 · macOS: Docker Desktop arm64)
 browser ──http://127.0.0.1:8000──┐   (getUserMedia: localhost is a secure context)
┌─────────────────────────── compose project "probeloop" ────────────────────────────┐
│ backend      FastAPI + built SPA · UrlGuard · VAD · orchestrator      [net: internal, egress] │
│ stt-worker   ProbeLoop speech worker: faster-whisper / Parakeet,                   │
│              image variants cpu | cuda                                [net: internal] │
│ tts-piper    unmodified Piper HTTP server, GPL, separate image        [net: internal] │
│ ollama       profile "nvidia": GPU reservation; omitted on Mac        [net: internal] │
│ postgres     profile "postgres" (SQLite on a named volume by default) [net: internal] │
│ frontend-dev dev only: Vite + HMR via `docker compose watch`                       │
│ volumes: data (DB, blobs, audio) · models (HF cache, voices) · ollama              │
└──────────────────────────────────────────────────────────────────────────────────────┘
```

**Why speech recognition and synthesis are separate services.** Each split addresses a concrete
constraint. This is not microservices for their own sake.

- **`tts-piper` isolates the GPL component.** Piper is a distinct, unmodified program in its own
  image, reached over HTTP.
- **`stt-worker` isolates heavy dependencies and hardware variants.**
  - CPU and CUDA images can be swapped without touching the backend.
  - Its own resource limits (`cpus`) stop speech recognition from starving the backend or Ollama.
  - On a Mac, Docker cannot use Metal. The same worker can then run natively with MLX, and the
    backend does not change.

The worker is not a separate project:

- It is a second entrypoint of the same package (`probeloop.speech.worker`), hosting the engine
  adapters in-process.
- It exposes a minimal internal API: `POST /transcribe` takes PCM audio and options, and returns
  segments, words and confidences.
- The backend talks to it through `HttpSpeechToText`.
- Tests use the in-process adapters or fakes.

Existing speech servers were considered and kept only as possible alternative adapters:

- **Wyoming** (OHF, MIT, actively maintained) offers only a global prompt, not one per request, and
  returns no per-word confidences. Both are needed to fight transcription errors.
- **speaches** (MIT) is still in release-candidate stage.

**Ollama.**

- **On machine A (Windows, 16 GB RAM), the native Ollama on the host is the default**, reached
  through `OLLAMA_BASE_URL=http://host.docker.internal:11434`. In M1, the containerised Ollama
  matched the native one once warm, but loading models through the WSL2 VM took 3–15× longer, and
  the VM competed for RAM ([spike results](research/spike-results.md) §2.1).
- The Compose `ollama` service (profile `nvidia`, GPU reservation, models in a named volume)
  remains available for Linux hosts with enough RAM.
- On a Mac, `OLLAMA_BASE_URL` points to the PC over the LAN.
- Two Ollama instances must not hold models at the same time, because they compete for VRAM.

## 7. Modules

The package is `probeloop`. The table below is the **target map**; section 7.1 explains when each
module actually appears.

| Module | Responsibility | Depends on |
|---|---|---|
| `shared` | Minimal kernel: UUIDv7 ids, `Clock`, domain errors, common value objects (`Language`, `DurationBudget`) | — |
| `ai` | LLM ports, capability descriptor, `StructuredGenerator` (validation and retry), versioned prompt templates, context guard (`prompt_eval_count` against `num_ctx`), LLM interaction log | `shared` |
| `speech` | STT and TTS ports, incremental turn transcription, sentence segmentation, audio formats, stt-worker entrypoint | `shared` |
| `context` | Documents, sources, extraction, enrichment, facts with evidence, review, snapshots, requirement matching | `shared`, `ai` |
| `interview` | Configuration, session and state machine, activities, turns, planner, interviewer, conversation memory, time policy, orchestrator | `shared`, `ai`, `speech`, `context` (public read API of the snapshot only) |
| `assessment` | Rubrics, evaluation pipeline, evidence validators, versioned reports, comparison queries | `shared`, `ai`, public reads of `interview` and `context` |
| `platform` | Settings, database engine and unit-of-work base, `BlobStore`, `JobRunner`, logging, `UrlGuard` | `shared` |
| `bootstrap` | Composition root: builds adapters from configuration, creates the FastAPI app, manual wiring | all |

**Internal structure of a business module:**

- `domain/` holds plain Python.
- `application/` holds the use cases and `ports.py`.
- `infrastructure/` holds the outbound adapters.
- `api/` holds the presentation layer: routers and Pydantic I/O schemas.

**Dependency rules**, enforced with import-linter:

1. `domain` imports only the standard library and `shared.domain`.
2. No module imports another module's `infrastructure`.
3. Only `bootstrap` knows concrete adapters.
4. `context` depends on neither `interview` nor `assessment`.

There is no dependency-injection framework, just an explicit container in `bootstrap` plus
FastAPI dependencies.

### 7.1 Initial layout

A module is created when it gets its first real consumer. Empty folders are not created for
symmetry. Layout for milestones M2–M3:

```
backend/src/probeloop/
  interview/domain/        session, state machine, TimePolicy, moves (pure Python)
  interview/application/   orchestrator, LLM interviewer, ports.py
  ai/                      ChatModel port, Ollama adapter, fake, structured-output helper
  speech/                  STT/TTS ports, TurnTranscriber, adapters (HTTP worker client, faster-whisper,
                           Piper HTTP, fakes); worker.py = stt-worker entrypoint (from M3)
  storage/                 file-based session store (JSON + audio per session dir), replaced in M4
  api/                     FastAPI app, REST, WebSocket gateway
  bootstrap.py             composition root
repo root: compose.yaml · compose.nvidia.yaml · compose.dev.yaml (watch) · docker/*.Dockerfile · frontend/ (from M3)
```

When the remaining modules appear:

- `context` in M5, `assessment` in M7.
- `platform` is split out when the first service shared by two modules appears (the job runner,
  in M5).

import-linter starts with a single rule: the domain does not import fastapi, sqlalchemy, pydantic,
ollama or adapters. Rules between modules are added once the modules exist.

## 8. Ports

The signatures below are indicative. Contract tests pin down the details.

```python
# ai/application/ports.py
@dataclass(frozen=True)
class ModelCapabilities:
    context_window: int
    streaming: bool
    structured_output: Literal["json_schema", "json_object", "none"]
    tool_calling: bool
    reasoning: bool            # supports a thinking/reasoning toggle
    vision: bool
    sampling_params: bool      # accepts temperature/top_p (some providers reject them)
    system_role: bool          # accepts system-role messages

class ChatModel(Protocol):
    @property
    def model_ref(self) -> ModelRef: ...                      # provider + model + options digest
    async def capabilities(self) -> ModelCapabilities: ...
    async def complete(self, request: ChatRequest) -> ChatResult: ...
    def stream(self, request: ChatRequest) -> AsyncIterator[ChatDelta]: ...

# ChatRequest: instructions (kept separate from messages), messages, response_schema (JSON Schema | None),
#   temperature, max_output_tokens, reasoning: Literal["off", "default", "high"], tools, seed,
#   context_window (num_ctx)
# ChatResult: text, parsed (if schema), usage (prompt/output tokens), timings, finish_reason

class ModelCatalog(Protocol):
    async def list_models(self) -> list[ModelInfo]: ...
```

```python
# speech/application/ports.py
class SpeechToText(Protocol):
    @property
    def engine_ref(self) -> EngineRef: ...                    # engine, model, version, device
    async def transcribe(self, audio: PcmAudio, options: TranscribeOptions) -> Transcription: ...
# TranscribeOptions: language, initial_prompt (vocabulary from the snapshot), word_timestamps
# Transcription: segments[start, end, text, avg_logprob, words?], language, engine_ref

class TextToSpeech(Protocol):
    async def voices(self, language: Language) -> list[Voice]: ...
    def synthesize(self, text: str, voice: VoiceId, options: SynthesisOptions) -> AsyncIterator[AudioChunk]: ...
```

```python
# context/application/ports.py
class DocumentTextExtractor(Protocol):
    async def extract(self, blob: BlobRef, media_type: str) -> ExtractedText: ...  # pages + offsets
class WebFetcher(Protocol):
    async def fetch(self, url: str, policy: FetchPolicy) -> FetchOutcome: ...
    # FetchOutcome = Fetched(page: WebPage) | Denied(reason) | Unavailable(reason)
class GitHubClient(Protocol):
    async def profile(self, login: str) -> GitHubProfile: ...
    async def public_repos(self, login: str, limit: int) -> list[RepoSummary]: ...
    async def repo_details(self, owner: str, name: str) -> RepoDetails: ...  # languages, readme, topics
```

```python
# persistence
class BlobStore(Protocol):
    async def put(self, data: AsyncIterator[bytes] | bytes, *, namespace: str) -> BlobRef: ...  # sha256
    async def open(self, ref: BlobRef) -> AsyncIterator[bytes]: ...
    async def delete(self, ref: BlobRef) -> None: ...
class SessionRepository(Protocol): ...   # get / add / save; same pattern for the other aggregates
class UnitOfWork(Protocol): ...          # async context manager, commit/rollback
```

```python
# interview/application/ports.py
class Interviewer(Protocol):
    def next_move(self, state: InterviewerInput) -> AsyncIterator[InterviewerMoveDelta]: ...
```

`Interviewer` is the only application-level port from day one. It hides the parsing of the
streamed move, and it lets the orchestrator be tested with a scripted implementation.

- `Planner` arrives in M5. Until then, topics come from a YAML file per interview type: there is
  no snapshot to plan from.
- `Evaluator` arrives in M7.

## 9. Domain model

### Context: knowledge about the candidate and the position

**`CandidateProfile`** is a long-lived aggregate, reused across sessions. **`JobPosting`** is an
aggregate.

**`Document`**
- `kind`: `cv`, `job_offer`, `attachment`, `web_page` or `github_repo`.
- `origin`: `upload`, `url` or `manual`.
- References: `blob_ref`, `sha256`, `media_type`, `extracted_text_ref`.
- Extraction status, including the extractor version.

**`Source`** records the provenance of a URL:
- canonical URL, `fetched_at` and content hash;
- outcome: `fetched`, `robots_denied`, `auth_required`, `not_found`, `unsupported`, `timeout` or
  `policy_denied`.

**`Fact`**
- `subject`: `candidate` or `job`.
- `category`: skill, experience, education, project, requirement, responsibility, and so on.
- `statement` and `attributes`.
- `origin`: `cv_statement`, `user_entry`, `external_source` or `model_inference`.
- `evidence[]`: `EvidenceRef(document_id, locator, quote, quote_verified)`.
- `confidence`.
- `review`: `pending`, `confirmed`, `corrected` (with `corrected_value`) or `excluded`.
- `produced_by`: the pipeline step, model and prompt version that created it.
- **UI badges:**
  - *Declared*: a CV statement or user entry.
  - *Observed*: an external source with verified evidence.
  - *Inferred*: a model inference.

**`RequirementMatch`**: `(requirement_fact, candidate_facts[], status, rationale)`, where `status`
is `met`, `partial`, `not_evidenced` or `unknown`.

**`ContextSnapshot`** is immutable. It holds:
- the included facts, serialized;
- the requirement matches;
- a compact interviewer brief;
- `content_hash` and `schema_version`.

Identical inputs reuse the same snapshot, found by hash.

### Interview

**`InterviewConfig`** (value object)
- `type`: hr, behavioral, technical or mixed; later system_design and live_coding.
- `difficulty`, `target_duration`, `language`.
- `model_profiles` (interviewer, evaluator) and `voice`.
- `custom_instructions`: length-limited text.
- `audio_retention`.

**`InterviewSession`** (aggregate root)
- `config`, `snapshot_id` and `plan`.
- `status` (macro state) and `phase` (turn micro state).
- `timing`: start, pauses and effective elapsed time.
- `activities[]` and `ended_reason`.

**`InterviewPlan`** has `topics[]`. Each topic has:
- an id and a title;
- a kind, a priority and the facts it refers to;
- a time weight;
- coverage: `not_started`, `in_progress`, `covered` or `skipped`.

**`Activity`**
- `kind`: `conversation` in the MVP; later `coding_exercise` and `system_design`.
- A status and a time interval.
- A conversation activity contains turns.
- Persisted from M5, one per session in the MVP.

**`Turn`**
- Common fields: `seq`, `speaker` (interviewer or candidate), `topic_id` and timestamps.
- **Interviewer turn**: `InterviewerMove(action, topic_id, covered_topic_ids, utterance, status)`,
  where `status` is `completed` or `interrupted`. It also records the `model_ref` and the prompt
  version.
- **Candidate turn**:
  - `audio_ref`;
  - `TranscriptRevision[]`: revision number, text, and segments with timestamps and confidences;
  - each revision's `source`: stt, user_edit or retranscription, with engine and model;
  - `current_revision`.

**`ConversationMemory`** is a deterministic projection that can be recomputed from the turns. It
holds the questions already asked and the topic coverage. LLM-generated summaries are added only
if measurements show they are needed (section 13).

**`TurnMetrics`**: `stt_finalize_ms`, `llm_ttft_ms`, `llm_total_ms`, `tts_first_audio_ms`,
`end_to_end_ms`.

### Assessment

**`Rubric`** is immutable per version.
- `id@version` and the interview types it applies to.
- `criteria[]`, each with an id, a description, a weight, a scale with level anchors, and evidence
  guidance.
- An aggregation rule.

**`EvaluationRun`** records:
- the session and a fingerprint of the transcript (the set of revisions used);
- the snapshot and the rubric version;
- the model and prompt versions;
- status and errors.

**`Report`** is versioned per session.
- Content: summary, strengths, improvements, answer analyses, technical errors, suggestions.
- Scores: `criterion_scores[]` and `overall_score`, computed in code.
- `validation_stats` and a disclaimer.

**`Observation`**
- `kind`: strength, improvement, objective_error, subjective_assessment or insufficient_evidence.
- `text`.
- `evidence[]`: `turn_id`, `quote`, `span` and `verified`.
- `criterion_ids`.

**`CriterionScore`** holds a score or `not_assessable`, a justification and `observation_ids`.

### Platform

- **`Job`**: type, status, progress, error.
- **`LlmInteraction`**: purpose, model, template version, request and response references, tokens,
  latencies, validation outcome, attempt number.

## 10. Interview orchestration

### 10.1 State machine

**Macro states**

```
DRAFT ─► READY ─► IN_PROGRESS ⇄ PAUSED
                      │
                      ├─► ENDED ─► EVALUATING ─► EVALUATED
                      └─► FAILED ─► (abort, or salvage to ENDED)
```

- `ENDED` can go back to `EVALUATING` after a transcript correction.
- `FAILED` can be salvaged to `ENDED`, keeping the partial transcript.

**Turn micro phases** (only while `IN_PROGRESS`)

```
INTERVIEWER_THINKING ─► INTERVIEWER_SPEAKING ─► AWAITING_CANDIDATE
        ▲                                               │ turn.start (user click)
        └── FINALIZING_TRANSCRIPT ◄── turn.end ◄── CANDIDATE_SPEAKING
```

**Preparation in `READY`.** This runs while the user reads the Phase D summary, so the session
starts without 10–20 seconds of silence:

- plan generation (from M5; before that, topics come from YAML);
- model preloading in Ollama, with the cold-load progress shown in the UI;
- **KV-cache priming**: after the plan exists, one request with the stable prompt prefix (system
  rules, brief, topics) fills the cache.
  - M1 measured the first token of a 5k-token prompt at 3.5–4.7 s on a fresh prompt, and at
    0.6–0.9 s when the prefix was cached.
  - With `OLLAMA_NUM_PARALLEL=1`, any other call to the same model evicts the cache. No other LLM
    work may therefore run during an interview;
- a microphone check with a level meter. The check also provides the user gesture that browsers
  require before they play audio.

**Responsibilities**

- **Pure domain.** The transition table lives in the `InterviewSession` aggregate. Illegal
  transitions raise, and table-driven tests cover every transition. No state-machine library is
  needed.
- **`SessionOrchestrator`** (application layer):
  - receives events from the WebSocket gateway;
  - invokes `Interviewer`, `TurnTranscriber` and `UtteranceSynthesizer`;
  - persists each step and emits events.

  One active session at a time is enough for a single-user application.
- **`TimePolicy`** (domain, a pure function). It takes the effective elapsed time (pauses
  excluded), the target duration and the plan state, and returns a directive:

  | Elapsed share of the target | Directive |
  |---|---|
  | Below 85% | `normal`, with per-topic remaining time as a hint |
  | 85% | `begin_wrap_up` |
  | 100% | `final_question` |
  | 115% | `force_close`: the orchestrator closes with a template farewell, without the LLM |

  Single answers have their own limit: a warning at 4 minutes and an automatic end at 6
  (configurable). The LLM decides how to distribute time across topics; the orchestrator
  guarantees the limits.
- **Errors.**
  - LLM: one retry, then a localised fallback phrase. The state is kept.
  - Speech recognition: the audio is kept, so the step can be retried.
  - Disconnection: see section 10.3.

### 10.2 The interviewer move

An interviewer move is a single streamed LLM call with **schema-constrained JSON output** (Ollama
`format`):

```json
{"action": "follow_up", "topic_id": "t3", "utterance": "...", "covered_topic_ids": ["t2"]}
```

- `action` is one of `follow_up`, `clarify`, `new_topic`, `present_exercise`, `wrap_up` or `end`.
- **The field order is fixed, and `utterance` comes before the bookkeeping field.** The stream is
  parsed incrementally (`pydantic_core.from_json(..., allow_partial="trailing-strings")`), and
  every complete sentence of `utterance` goes to TTS as soon as it exists.
- **No reasoning field precedes the utterance**, and reasoning mode stays off.
- **The choice is measured (M1, [ADR 0011](adr/0011-interviewer-move-format.md)):**
  - constrained JSON was valid in 100% of 90 moves across three models, and the field order was
    respected every time;
  - time to the first complete sentence was the same as with a plain-text "header + text" format
    (p50 0.8–1.0 s);
  - the header format was valid in only 76–95% of moves.
- Constrained JSON is also the format for the planner, the extractor and the evaluator.

**One question per turn, enforced in code.**
- In M2 the persona evaluations showed `ministral-3:8b` appending sub-questions ("Per
  esempio…?") to most turns, even with an explicit rule in the prompt.
- The interviewer therefore cuts the utterance at its first question mark, both in the stream and
  in the recorded move. The extra text never reaches the client or the speech synthesiser.
- The farewell (`end`) is exempt, and so are markdown emphasis characters, which are removed
  before speech.
- This sits alongside the time limits: the model decides what to ask, and the code guarantees the
  shape of the turn.

### 10.3 Runtime details

- **Microphone and echo.**
  - The microphone track stays open, but **the server discards audio frames outside
    `CANDIDATE_SPEAKING`**.
  - An answer starts only with an explicit click, never automatically after
    `playback.finished`.
  - `getUserMedia` is called with `echoCancellation` and `noiseSuppression`.
  - Denied permissions and device changes (`devicechange`) are recoverable states shown in the UI.
- **Speech recognition engines** ([ADR 0009](adr/0009-speech-recognition.md)):
  - **Live**: Parakeet TDT 0.6B v3 (int8, onnx-asr) transcribes each VAD segment. M1 measured a
    tail of about 0.4 s after the click.
  - **Refinement**: when the interview ends, a faster-whisper large-v3-turbo full pass with
    snapshot-vocabulary biasing produces the transcript revision that the user reviews and the
    evaluator uses.
  - Whisper cannot serve the live path on the CPU. Its fixed 30 s window makes every segment cost
    nearly the same, which gave an 11–13 s tail in M1.
- **Speech recognition and the event loop.**
  - The worker processes segments one at a time.
  - The engine thread pools are bounded (indicatively 6–8 threads) to leave room for the backend,
    Piper and the browser.
  - onnxruntime and CTranslate2 release the GIL.
- **Recognition edge cases.**
  - A segment is force-cut at 15 s even without a pause, so the tail left after the click stays
    short.
  - Defences against hallucinated text on silence (M1: "Grazie." on silence without VAD):
    - VAD gating;
    - `condition_on_previous_text=False` for Whisper;
    - a minimum segment length;
    - a blocklist of known phrases.
- **Ollama.**
  - The model is preloaded in `READY`, kept loaded with an extended `keep_alive` during the
    session, and released at the end.
  - **There is one `num_ctx` per loaded model.** A different value forces Ollama to reload it.
- **Cancellation.**
  - Each move is a cancellable asyncio task.
  - On `session.end`, pause or disconnection:
    1. the Ollama stream is closed, and Ollama stops generating;
    2. the TTS queue is flushed;
    3. the move is marked `interrupted`.
  - On resume, the move is regenerated only if no sentence had been spoken yet. Otherwise the
    session continues from where it stopped.
- **Piper and stt-worker.**
  - Both are Compose services with healthchecks and `restart: unless-stopped`. The backend does
    not manage child processes.
  - When a session starts, the backend checks the services' health and shows their status. An
    unavailable service blocks the start with a clear message.
- **Time.** A monotonic server-side `Clock` is authoritative. The client only displays what it
  receives in `timer` messages.
- **Reconnection.**
  - Only one WebSocket connection per session is allowed; a second tab is rejected.
  - Control messages carry a `client_msg_id`, so duplicates (for example a repeated `turn.end`)
    are ignored.
  - The server replays the events after the last known `seq`.
  - Binary PCM frames carry no sequence number. If the connection drops during an answer:
    - the audio received so far stays in the turn;
    - the turn goes back to `AWAITING_CANDIDATE`;
    - a new `turn.start` *appends* to the same turn, or the candidate chooses "restart answer".

### 10.4 Avoiding repetition

Repetition is prevented in the prompt: the questions already asked and the topic coverage are
part of the input. Suppressing a repeated question at runtime is impossible, because with
per-sentence TTS the first sentence has already been spoken by the time the question is
complete.

Repetition is **measured** offline in the interviewer evaluations (section 20). The measurement
uses `rapidfuzz` lexical similarity on simulated conversations with scripted candidates. It is
not done by the same mechanism that is supposed to prevent it.

## 11. Session flow

1. **Phase A.** Create the profile and the posting. Upload the CV and the job offer (PDF, text or
   URL) and enter extra links. A draft configuration is created.
2. **Phase B.** An `analyze_context` job is queued. Its progress is exposed through polling.
   1. Blobs are stored, deduplicated by sha256.
   2. Text is extracted in a process pool with a timeout.
   3. Sections are extracted into structured data, each item with a `source_quote`.
   4. Quotes are verified, and each fact is assigned its origin and evidence.
   5. Links are collected and enrichment is queued (M8).
   6. The requirement–fact matrix is computed.
3. **Phase C.** The user reviews the facts: confirm, correct, exclude, add manual entries, or upload
   new documents (analysed incrementally). Approval creates the `ContextSnapshot` and the
   interviewer brief.
4. **Phase D.** The summary is shown, then `POST /sessions` moves the session to `READY`. While the
   user reads the summary, the system generates the plan, preloads the model and runs the
   microphone check.
5. **Phase E.** The WebSocket opens and the client sends `session.start`.
   1. The first move delivers the opening. Its sentences are streamed to TTS and played back.
   2. The client sends `playback.finished`, and the phase becomes `AWAITING_CANDIDATE`.
   3. The candidate clicks "answer" (`turn.start`). PCM frames flow in, and incremental partial
      transcripts come back as `transcript.partial`.
   4. The candidate sends `turn.end`. The transcript is finalised and sent as `transcript.final`;
      the audio, the revision and the metrics are stored.
   5. The next move follows, and so on, until `wrap_up`/`end` or the `TimePolicy` closes the
      session (`ENDED`).
6. **Phase F.**
   1. When the call ends, a refinement job re-transcribes the stored audio with Whisper turbo and
      creates a `retranscription` revision for every turn. The UI shows the job's progress.
   2. The transcript editor then creates a new revision for every correction.
   3. "Generate report" queues an evaluation job, which produces report v1. After further
      corrections it can produce v2.
7. **Phase G.** The history shows past sessions and compares per-criterion scores. A comparison is
   valid only when both sessions used the same rubric version; otherwise the UI flags it.

## 12. Frontend–backend communication

**Frontend structure (M6, ADR 0014).** The React SPA follows Feature-Sliced Design:
`app → pages → widgets → features → entities → shared`. Imports point downwards, same-layer
slices do not import each other, and every slice has a public entry point. Steiger checks these
boundaries. The transitional legacy screens and translation map have been removed.

Pure view models prepare report sections, numbered answers, requirement coverage, delivery
medians and conversation blocks. Components render those views; typed English and Italian
dictionaries live with their consumers. Fonts are served locally. The shell keeps navigation
fixed, scrolls the content below it, and uses the same page width, headings and breadcrumbs.
Short lists show newest records first with pagination. Trend lines join scores only within the
same evaluator key and interview type, with a table alternative.

The five preparation steps are routes under `/new-interview`. A versioned Zustand draft persists
in `sessionStorage` until the interview starts. Back always remains available; forward navigation
requires the preceding steps. TanStack Query owns server data. Each preparation and interview
stores its execution profile (ADR 0015); later analysis and report jobs use that profile rather
than the default currently selected in Settings. Speech recognition and synthesis remain local.

**Report presentation contract.** The pure Python `assessment/application/outline.py` prepares
the localized Markdown and PDF outline. The API obtains question text and frozen answer
revisions through the assessment service, plus CV requirements from the immutable snapshot.
Raw JSON exports remain `ReportData`. The shared fixture
`backend/tests/fixtures/synthetic/assessment/report-outline.json` is checked against the outline
by pytest and against the frontend view models by Vitest. Component tests also pin the rendered
section order. Technical hashes are shortened and kept at the end; per-answer delivery rows
form an appendix. PDF templates escape data and refuse all external resource fetching.

**REST + JSON** handles all CRUD and jobs. Job status is polled with TanStack Query. Server-sent
events are a later improvement, added only if polling proves insufficient.

**One WebSocket per live session** carries typed JSON messages and binary audio frames.

- Client to server: `session.start`, `turn.start`, PCM16 frames, `turn.end`,
  `playback.finished`, `session.pause`, `session.resume`, `session.end`, `ping`.
- Server to client: `state.changed`, `interviewer.text.delta`, `tts.chunk` (metadata followed by a
  binary frame), `transcript.partial`, `transcript.final`, `timer`,
  `error{code, recoverable}`, `session.ended`.
- Every message carries a `seq`. The server holds the authoritative state.

**Shared contracts** are generated:

- OpenAPI → `openapi-typescript`;
- Pydantic models of the WebSocket messages → JSON Schema → `json-schema-to-typescript`.

A script regenerates the types, and CI fails if they change.

**Browser audio.**

- **Capture**: an AudioWorklet downsamples to 16 kHz mono PCM16, which is Whisper's native input.
  No decoding or ffmpeg is needed on the server. The stream is about 32 KB/s.
- **Playback**: PCM chunks are converted to `AudioBuffer`s and scheduled back-to-back on the
  `AudioContext` clock.

## 13. LLM context management

- **Always pass `num_ctx` explicitly**, one value per loaded model.
  - Ollama's default is 4096 on GPUs below 24 GB, and the advertised 262k context is not usable
    on 8 GB.
  - The value is **8192** on machine A. In M1, 16k pushed 0.8–1.3 GB of an 8–9B model onto the CPU
    and cut generation from about 42 to about 30 tokens/s.
- **Hard check instead of elaborate budgeting.** Ollama truncates prompts silently, so:
  - before a request, a conservative estimate is made (characters per token);
  - after it, `prompt_eval_count` is compared with `num_ctx`;
  - overflowing, or a margin below 10%, produces an explicit error or a metric warning, never
    silent truncation.
- **Append-only prompt layout**, to maximise KV-cache prefix reuse:
  1. system rules and configuration;
  2. the candidate brief (from M5) and the static topic list;
  3. the transcript, which only grows at the end;
  4. volatile state last: topic coverage, questions already asked, time directive.

  How much of the prefix Ollama actually reuses with qwen3.5's hybrid architecture is *to be
  measured*. M1 compares time to first token with an unchanged prefix and with a modified one.
- **Deterministic windowing.** A 10–15 minute interview (3–5k tokens) fits in 8k. For longer
  interviews, once a threshold is exceeded, the oldest turns are replaced by a deterministic digest:
  the interviewer's questions plus topic coverage, with no LLM call. An LLM-generated running
  summary is added only if measurements show it is needed, because it costs an extra call during
  the interview.
- **The evaluator never receives an oversized transcript in a single prompt.** It works per
  segment. Segments follow the topics, which are known deterministically from the recorded moves.
  Each segment comes with a global summary and the full surrounding exchange. A synthesis step then
  works over the resulting observations.

## 14. Structured output, validation and retry

`StructuredGenerator` runs the same pipeline for every non-realtime use.

1. **Constrained decoding** when `capabilities.structured_output == "json_schema"` (Ollama
   `format`). Otherwise JSON mode with the schema in the prompt, otherwise extraction from free
   text.
2. **Pydantic validation**: types, enums and lengths.
   - Schemas are flat, with enums and short fields.
   - Large outputs are split into several calls.
3. **Injectable semantic validators**, for example:
   - referenced turn and fact ids exist;
   - quotes appear in the source (`rapidfuzz.partial_ratio` above a threshold, on normalised text);
   - scores stay within the scale;
   - every score has at least one observation, or is `not_assessable`.
4. **Repair retry** (at most 2): the exact errors are fed back to the model.
5. **Explicit degradation.**
   - Invalid items are dropped and counted in `validation_stats`.
   - Sections may be marked partial.
   - Data is never invented to fill a gap.

Settings: low temperature for extraction and evaluation, and a fixed seed where supported.

**Phased introduction**

| Milestone | Added |
|---|---|
| M2 | Constrained decoding, Pydantic validation and one repair retry. A JSONL debug log of LLM calls behind a flag. `model_ref` and prompt version stored on every move or artifact. |
| M5 / M7 | Semantic validators and `validation_stats`. |
| M6 | The `LlmInteraction` table, together with the diagnostics panel. |

## 15. Document pipeline and evidence

**Parsing**

- `pypdf` (BSD) or `pdfplumber` (MIT), chosen in M5 on synthetic CVs.
- `pdfplumber` exposes character colour and size, which allows **invisible text to be flagged**.
- PyMuPDF is excluded for licensing reasons (AGPL).
- Docling is a heavier future option.
- OCR is out of scope for the MVP.

**Extraction** is done section by section. Schemas:

- CV: a subset of JSON Resume.
- Job offer: title, company, seniority, must-have and nice-to-have requirements,
  responsibilities, language.

Every item carries a `source_quote`:

| Quote | Result |
|---|---|
| Found in the source text | Origin `cv_statement` with `quote_verified=true` |
| Not found | Origin `model_inference`, flagged for review |

**Reuse.** Extractions are keyed by document sha256, extractor version, prompt version and model,
and they are not recomputed if none of these changed.

**Enrichment (M8)**

- **GitHub.**
  - REST API; an optional token is read from the environment (`.env` or a Compose secret).
  - Data collected: profile, public non-fork repositories ordered by activity, languages, READMEs
    and topics.
  - Deterministic metrics become `external_source` facts. README summaries become
    `model_inference` facts with quotes.
- **Web.**
  - A deterministic crawler fetches pages, extracts the main content (`trafilatura`) and collects
    links.
  - A budgeted agent decides which collected links to follow:
    - only within an allowlist (the seed domains plus github.com);
    - at most N pages, depth 2.
  - The agent has **one tool**, `fetch_candidate_link(link_id)`. It accepts only ids of links
    already collected, never free-form URLs.
- **Unavailable sources** (LinkedIn, login-protected pages, `robots_denied`) are shown as such,
  with a suggestion to upload a PDF or paste the text.

## 16. Rubrics and reports

**Rubric files**

- Rubrics are YAML files in `backend/src/probeloop/assessment/rubrics/<type>.v<N>.yaml`.
- They are validated with Pydantic at startup. Reports retain their component version references
  and combined content hash; historical rubric files and reports remain unchanged.
- The criteria are language-independent; their descriptions are translated.

**Criteria by interview type**

| Type | Criteria |
|---|---|
| Technical v2 | Accuracy, technical depth, problem solving, trade-offs, practical experience, communication of reasoning, individual contribution |
| HR v1 | Motivation, relevant experience, career narrative, communication |
| Behavioral v1 | Ownership, specificity, results, reflection, depth under follow-up |
| Hypothetical v1 | Clarification, action plan, reasoning, risks, validation plan |
| Mixed | Each answered unit uses its question's rubric; criterion identifiers retain the rubric namespace |

Technical v2 adds individual contribution separately from practical experience. It concerns the
actions and responsibility established by an answer, without automatic pronoun, metric or paid-work
rules. It is unavailable when no question asked for an actual past example. Reports identify the
complete rubric set, including `technical.v2`, and its changed hash creates a new progress group.
See the [approved anchors](proposals/2026-11-technical-ownership-calibration.md).

**Evaluation pipeline**

1. Group recorded follow-ups with their answers; exclude a trailing unanswered question from
   assessment while preserving it in the transcript.
2. Classify question focuses and whether a past example was requested, using questions only.
3. Judge each unit twice, with ascending and descending anchors. Each pass requires every
   criterion and produces quotations before a reason and score; unavailable scores are allowed.
4. Verify candidate quotations, apply elicitation guards, and independently check proposed
   technical corrections. Corrections remain model opinions, including when both calls agree.
5. **Aggregate in code**: average both passes, then average available unit scores per criterion
   with equal criterion weights. Missing scores remain explicit; insufficient coverage prevents
   an overall score.
6. Select existing observations by identifier for the summary and suggestions. The synthesis
   cannot add evidence. Rewrites preserve source facts and numbers.

**Separation from the interviewer**

- The evaluator has its own templates, its own rubric and its own inputs: the corrected
  transcript, the confirmed snapshot and the configuration.
- It receives neither the custom instructions nor raw web content.
- Voice answers use their latest transcript revision. Users can inspect low-confidence words,
  listen and correct them before assessment. Recognition errors can still affect model feedback;
  the voice acceptance notes record this remaining evaluation limitation.

Every report carries a fixed disclaimer: scores are formative measures, not predictions of
hiring outcomes.

## 17. Persistence

### Adaptive policy and public score scale

[ADR 0016](adr/0016-adaptive-role-based-interviews.md) introduces `adaptive.v1` for newly
confirmed role profiles. Migration `0006` adds nullable preparation JSON; snapshot and session
JSON retain the complete reviewed facts, source-linked objectives and confirmed expectations.
Legacy sessions retain their original interviewer and assessment policy.

The planner defines objectives rather than a question script. The next move uses the actual
answer and relevant whole facts. Code derives action, latest-answer reference and hint level
from a small model choice, validates documentary ids and elicited criteria before audio, and
limits hints to two for an existing solvable problem. A transcript-introduced topic remains
linked to that answer, never retroactively attributed to the CV. Persisted engagement time
excludes pauses and model/STT/TTS delays. Topic windows share remaining time by priority within
45–240 seconds and yield to global closing.

Recorded question intent governs new-policy assessment; the profession-neutral classifier is
diagnostic. The new rubrics are `technical.v3`, `hr.v2`, `behavioral.v2` and `hypothetical.v2`.
They share autonomy anchors and aggregate it once as `common.autonomy`. Both numeric scores and
prose observations must belong to the actual elicited subset; past-only criteria also require
a past-example question. Double judging, verified candidate quotations and independent checks
of proposed corrections remain. Editorial synthesis selects observation ids only; code builds
the scope summary. Specialist interpretations are fallible model opinions, even with supplied
reference documents or two agreeing model readings.

Judges and calibration keep anchored 1–5 values. `ReportData` writes and returns an explicit
`scale: "0_100"` with `(value - 1) * 25`; it reads old JSON without a scale as 1–5. JSON retains
precision for lossless persistence; UI and Markdown/PDF round reading values to integers.
Missing values never become zero. History and progress endpoints use the public scale too.
Comparability keys include target expectations and policy; the dashboard uses the same boundary
before displaying a delta. The shared outline fixture checks frontend/export parity.

The [validation protocol](research/adaptive-interview-validation.md) keeps development cases
separate from held-out professions and requires post-generation source/persona audits.

**Database**

- SQLite by default, with WAL and foreign keys enabled. PostgreSQL is supported (Compose profile
  `postgres`).
- **SQLAlchemy 2.x in async mode** (aiosqlite / asyncpg), because the whole realtime path is
  async.
- Alembic with `render_as_batch=True`, so ALTERs work on SQLite.
- ORM models are separate from domain entities, with explicit mapping in the repositories.
- JSON columns hold flexible payloads. Ids are UUIDv7.
- Until M4, a file-based session store (a JSON document plus audio in one directory per session)
  keeps deletion simple: a session is removed together with its directory.

**Compose volumes**

- The SQLite database, blobs and audio live in the **named volume `data`**, mounted at `/data`.
- Bind mounts from NTFS are avoided: they are slow on Docker Desktop for Windows, and SQLite's WAL
  and locking are unreliable on them.
- Model caches and voices live in the volume `models`; Ollama models live in the volume `ollama`.
- Backup and export run through a dedicated `docker compose run` command (M9).

**Blobs**

- Stored on the filesystem under `/data/blobs`.
- Documents are content-addressed by sha256.
- Audio goes to `sessions/<id>/turns/<turn>.wav`, as PCM16 WAV written with the standard-library
  `wave` module. FLAC may come later.

**Retention and deletion**

- The audio retention policy is applied by a job after the report, or on request.
- "Do not store" disables re-transcription, and the UI says so.
- Deleting a session, profile or posting cascades to its blobs. "Delete all my data" is available.

Models and voices are never stored in the repository or in images.

## 18. Security

### 18.1 Network

- The backend is published on `127.0.0.1` only, with a restrictive CORS policy.
- **`TrustedHostMiddleware`** accepts only `localhost` and `127.0.0.1`. This also protects the REST
  API against DNS rebinding.
- A JSON content type is required on mutating requests, and the `Origin` header is checked on the
  WebSocket.
- These protections apply from M2.
- **LAN exposure** is opt-in. It requires a token and HTTPS (for example a Caddy reverse proxy),
  because outside `localhost` browsers allow `getUserMedia` only in a secure context.
- **A remote Ollama** must be reachable only on the LAN or behind an authenticating reverse proxy:
  Ollama has no authentication of its own.

### 18.2 Container hardening

- **Ports are published on `127.0.0.1` only** (`"127.0.0.1:8000:8000"`); Compose publishes on all
  interfaces by default.
- Only the backend is published. `stt-worker`, `tts-piper`, `ollama` and `postgres` stay on the
  `internal` network with no published ports.
- Containers run as a non-root user, with `cap_drop: [ALL]` and `no-new-privileges`. They are
  `read_only`, with `tmpfs`, where possible.
- **The Docker socket is never mounted** into an application service.
- In M8 the crawler's fetcher may become a separate service on an egress-only network that cannot
  reach the internal services. That adds network-level SSRF protection on top of `UrlGuard`.

### 18.3 Uploads

- Size limits and magic-byte checks.
- Parsing runs in a process pool, with a timeout and a page limit.

### 18.4 `UrlGuard`

`UrlGuard` covers both the crawler and job-offer URL fetches.

- Only `http` and `https`, on ports 80 and 443, with no credentials in the URL.
- DNS is resolved, and private, loopback, link-local, metadata and reserved addresses are blocked:
  - the check is repeated on every redirect (at most 5);
  - the resolved IP is pinned, against DNS rebinding.
- `robots.txt` is honoured (`protego`). Requests carry an identifiable User-Agent and are
  rate-limited per host.
- A size limit (2 MB), a time limit and a content-type allowlist apply.
- No cookies and no JavaScript. Playwright may come later as an optional, sandboxed component.

### 18.5 Prompt injection

- External content is delimited and declared as data.
- Invisible text and suspicious patterns are flagged during review.
- Extraction calls have no tools. The enrichment agent has a single constrained tool.
- Every fact needs verified evidence, or it stays *inferred*.
- Human review happens before the snapshot is frozen.
- The evaluator never sees raw external content.
- Custom instructions sit in a section with lower priority than the system rules, and they cannot
  affect rubrics or scores.

### 18.6 Secrets

- Secrets are read from environment variables, loaded from a git-ignored `.env` (with a committed
  `.env.example`) or from Compose secrets.
- They never go into the database, the logs or the images.
- The OS keyring is not reachable from containers.
- `gitleaks` runs in CI, and optionally in pre-commit.

### 18.7 Code runner (future)

- Code runs in a dedicated service: never in the backend, and never through the Docker socket.
- Limits: no network, a read-only filesystem, no capabilities, pid, memory and CPU limits, a
  non-root user, timeouts.
- Piston (MIT) is a candidate adapter. Which nested isolation (nsjail, gVisor) works on Docker
  Desktop is still to be verified.

## 19. Portability and providers

**The application always runs in Linux containers.** Windows and macOS differences therefore come
down to Docker Desktop, an optional external Ollama and the browser. There are no OS-specific
code paths.

- **Multi-arch images** (amd64 and arm64) are built with `docker buildx`.
- **Hardware variants are image targets and Compose overrides**, not code branches.
  - `stt-worker:cpu` and `stt-worker:cuda`.
  - `compose.nvidia.yaml` adds GPU reservations to `ollama`, and optionally to `stt-worker`.
- **The device is chosen in configuration** (`cpu|cuda`). It is probed at startup and the result
  is shown in diagnostics. Metal applies only to a worker running natively on a Mac.
- **Development** uses `docker compose -f compose.yaml -f compose.dev.yaml watch`.
  - Code is synced into the containers, where uvicorn `--reload` and Vite HMR pick it up. This
    sidesteps the missing file-change events from NTFS into WSL2.
  - Tests, linting and type checks run through `docker compose run --rm backend …`.
  - The host needs only Docker and git.
- **Resource sizing.** The WSL2 VM's memory and CPU (`.wslconfig`) are sized in M1. By default
  WSL2 takes half of the RAM, which leaves little margin with 16 GB and Ollama running inside
  WSL2. On an 8 GB Mac the Docker Desktop VM must stay small; Ollama does not run there.
- `.gitattributes` enforces LF line endings, so scripts and mounted files work in containers.

**Model profiles per role** (interviewer, extractor, evaluator, planner) each define `provider`,
`base_url`, `model`, `num_ctx` and `reasoning`.

**Execution profiles** ([ADR 0013](adr/0013-cloud-execution-profile.md)) choose between the local
models and ChatGPT models used through the user's ChatGPT plan (Sign in with ChatGPT) for the
interviewer, analysis and evaluation roles, from Settings. Speech always stays local.

- On a Mac, pointing `base_url` at the PC's Ollama is enough.
- Roles sharing the same Ollama model must use the same `num_ctx`. Configuration validation
  enforces this, because a different value forces a reload.
- Capabilities are read from the provider (`/api/show` → `capabilities`) and degrade explicitly.
  For example, without `json_schema` support the system uses JSON mode with retries.

## 20. Testing, CI and observability

### 20.1 Tests

- **Domain**: table-driven state-machine tests, `TimePolicy` with a fake clock, evidence
  validators, score aggregation. Hypothesis stateful tests are added only if the state machine
  grows, for example with coding activities.
- **Application with fakes**: a scripted `FakeChatModel` that also records requests, `FakeSTT`,
  `FakeTTS` and in-memory repositories. Complete interviews run in milliseconds.
- **Contract tests per port**: the same suite runs against every adapter (fake, live Ollama,
  SQLite, PostgreSQL, filesystem, the stt-worker over HTTP).
- **Integration**:
  - repositories on SQLite and PostgreSQL;
  - Alembic migrations up and down;
  - `UrlGuard` and the crawler against `respx` and a local server (SSRF, redirects, robots).
- **LLM quality**: synthetic labelled datasets in `evals/` (fictional CVs, transcripts with known
  facts).
  - Extraction is measured on precision and recall, the verified-quote rate and hallucinations.
  - **The interviewer itself** is evaluated with 3–5 scripted candidate personas, for every new
    prompt version:
    - automatic checks: near-duplicate question rate, correct language, one question per turn
      within a word limit, topic coverage, timing;
    - sampled manual or LLM-judged checks: no invented CV facts, and follow-ups relevant to the
      last answer.
  - These evaluations run locally with real models (`pytest -m live` or a script), not in CI.
- **Frontend**: Vitest and Testing Library, MSW for the API, and the WebSocket client tested
  against a mock server.
- **End-to-end**: Playwright against the Compose stack in the `test` profile, which uses fake
  adapters. Chromium runs with `--use-fake-device-for-media-stream
  --use-file-for-fake-audio-capture=<wav>`, which covers the whole audio path without a GPU.

### 20.2 CI

CI runs on **GitHub Actions, ubuntu runners only**. The application always runs in Linux
containers, so Windows and macOS matrices (which are costly on private repositories) are not
needed.

- Image builds use buildx caching.
- Backend checks run inside the container: ruff, mypy `--strict`, pytest, import-linter.
- Frontend: lint, `tsc`, Vitest, build.
- End-to-end tests run with Compose and Playwright.
- arm64 builds run only on `main`.
- Dependabot covers pip, npm, docker and actions. gitleaks scans for secrets.

### 20.3 Observability

- Structured JSON logging with `session_id`, `turn_id` and `job_id` carried through contextvars.
  No personal data is logged at INFO level.
- `TurnMetrics` and LLM interactions are stored in the local database and shown in a diagnostics
  panel.
- OpenTelemetry is optional, later.

## 21. Evolution towards live coding

These elements are already part of the design, so live coding needs no structural changes:

- `Activity` as a polymorphic entity;
- the `present_exercise` interviewer action;
- an extensible union of WebSocket messages;
- `CodeRunner` as a port.

What still has to be added:

1. A `coding_exercise` activity: problem statement, examples, constraints, language, visible and
   hidden tests, debounced code snapshots, runs.
2. A "shared screen" panel with Monaco (`@monaco-editor/react`).
3. Messages `activity.started`, `code.snapshot`, `code.run.request` and `code.run.result`.
4. Code diffs and test results, summarised into the interviewer's context.
5. A coding rubric combining deterministic test results, an LLM review of the code, and the
   conversation.

Exercises preferably come from a curated bank with tests, because LLM-generated tests are
unreliable. The runner follows section 18.7. A dedicated design document is required before this
milestone starts.

## 22. Abstractions: now versus later

**Now (M2–M3).** Each has a real consumer.

- `ChatModel` with Ollama and fake adapters, plus a structured-output helper with a single retry.
- `Interviewer`, the only application-level port.
- `SpeechToText` and `TextToSpeech`, each with one real adapter and one fake.
- `Clock`.
- A file-based `SessionStore`.
- The import-linter rule on the domain.

**Introduced with the milestone that uses them**

| Milestone | Abstractions |
|---|---|
| M4 | SQLAlchemy repositories and unit of work, `BlobStore`, PostgreSQL. PostgreSQL support is cheap and prevents SQLite-only constructs from the first migration. |
| M5 | Persisted `Activity`, `Planner`, `JobRunner`, `DocumentTextExtractor`, `UrlGuard`, semantic validators |
| M6 | `LlmInteraction` table with the diagnostics panel |
| M7 | `Evaluator` |
| M8 | `WebFetcher`, `GitHubClient`, enrichment agent |
| M10 | `CodeRunner` |

**Deferred until measurements or usage justify them**

- an event bus (the gateway forwarding orchestrator events is enough for now);
- an LLM-generated running summary;
- client-side TTS with Web Speech. It is not a drop-in fallback: timing, metrics and sentence
  splitting would move to the browser, and Chrome's `speechSynthesis` `onend` event is unreliable
  on long utterances;
- Hypothesis stateful tests;
- SSE, OpenTelemetry and an S3 blob store;
- LAN authentication;
- further STT/TTS engines (for example MLX on a Mac);
- voice activity detection for barge-in.

## 23. Decision records

| ADR | Decision | Written |
|---|---|---|
| [0001](adr/0001-modular-monolith-hexagonal.md) | Pragmatic hexagonal modular monolith; a module appears with its first consumer | M0 |
| [0002](adr/0002-technology-stack.md) | Python 3.13 + FastAPI + uv; React + TypeScript + Vite | M0 |
| [0003](adr/0003-llm-provider-port.md) | Thin LLM port with a native Ollama adapter | M0 |
| [0004](adr/0004-persistence.md) | File-based session store until M4, then SQLite by default with async SQLAlchemy; PostgreSQL supported | M0 |
| [0005](adr/0005-realtime-transport.md) | Custom WebSocket protocol, PCM16 audio, explicit turn-taking | M0 |
| [0006](adr/0006-single-user-local-first.md) | Single user, local-first, no authentication in the MVP | M0 |
| [0007](adr/0007-licensing-policy.md) | Apache-2.0; no AGPL in-process; GPL only as separate programs | M0 |
| [0008](adr/0008-docker-compose-runtime.md) | Docker Compose as the supported runtime and development environment | M0 |
| [0009](adr/0009-speech-recognition.md) | Parakeet on CPU for live transcription; Whisper turbo refinement pass after the interview | M1 |
| [0010](adr/0010-speech-synthesis.md) | Piper in its own container; default voice pending a listening test | M1 |
| [0011](adr/0011-interviewer-move-format.md) | Constrained JSON for the interviewer move, parsed incrementally | M1 |
| [0012](adr/0012-interview-evaluation-pipeline.md) | Evidence-first interview judging without thinking; both anchor orders kept | M7 |
| [0013](adr/0013-cloud-execution-profile.md) | Optional cloud execution profile through Sign in with ChatGPT (plan usage); speech stays local | M7 |
| [0014](adr/0014-frontend-architecture-and-identity.md) | Frontend in Feature-Sliced Design with view models; typographic identity | M6 |
| [0015](adr/0015-execution-profile-per-interview.md) | Execution profile stored per preparation and interview | M6 |
| (planned) | In-process job runner with database-backed jobs | M5 |
| (planned) | Prompts and rubrics as versioned files | M2 / M7 |
| (planned) | Evidence-grounded evaluation with score aggregation in code | M7 |
