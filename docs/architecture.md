# Architecture

Current implementation, updated 2026-11-12. Decisions are recorded in [ADRs](adr/); dated
proposals, research and handoffs preserve earlier alternatives and measurements. Use the
[installation](getting-started.md), [configuration](configuration.md) and
[operations](operations.md) guides for current runtime instructions.

## Boundaries

ProbeLoop is a modular monolith using ports and adapters. Business dependencies point toward
plain domain and application code. Provider, engine and storage variability has explicit ports;
concrete adapters are selected only in the composition root, `probeloop.bootstrap`. There is no
DI framework, service locator or framework dependency in domain code.

| Module | Owns |
|---|---|
| `interview` | Session state, adaptive interviewing, planning, transcripts and revisions |
| `context` | Documents, extraction, reviewed facts, profiles, preparations and snapshots |
| `assessment` | CV/interview reports, rubrics, evidence checks and presentation exports |
| `speech` | Audio, VAD/segmentation, recognition/synthesis ports, adapters and worker |
| `ai` | Chat-model port, capabilities, provider adapters and scoped execution routing |
| `platform` | Persisted job runner and background model-access coordination |
| `storage` | SQL adapters, migrations, owned blobs and portable data operations |
| `workspace` | Machine tool selections, installation use cases and data-operation coordination |
| `api` | HTTP/WebSocket schemas, validation and transport mapping |
| `bootstrap` | Concrete composition, lifecycle and cross-module coordination |

Import-linter checks domain purity, application/adapter separation and business-module boundaries.
Installation use cases import neither the provisioner implementation nor web/provider SDKs.
New ports need real consumers; future engines or modules are not added speculatively.

The frontend follows Feature-Sliced Design: app composition/router, pages, features, entities and
shared primitives/API contracts. Slices expose public entrypoints. React Query coordinates server
state; local preferences remain separate from server-side machine/tool settings.

## Runtime

Docker Compose is the supported runtime and development environment. Packaged installations need
Docker Desktop; source development additionally needs git. Python, Node and checks run in
containers. Public runtime images have native amd64 and arm64 variants; the installer pins image
digests rather than a mutable latest tag.

| Service | Role | Model access |
|---|---|---|
| `backend` | FastAPI, built SPA, application use cases, CPU Laya session | Read-only |
| `provisioner` | Internal catalogued model installation over HTTP | Writable |
| `stt-worker` | Offline CPU Parakeet live ASR and optional Whisper refinement | Read-only |
| `tts-piper` | Unmodified Piper HTTP server as a separate program | Read-only |
| `postgres` | Optional source-deployment database profile | Separate database volume |
| `frontend-dev` | Vite hot reload, development overlay only | None |

Only the backend is published, on `127.0.0.1`. Speech services use an internal network without
external routes. The provisioner has outbound connectivity for HTTPS model downloads and is not
published. The backend reaches the configured cloud provider or native/remote Ollama; native
host Ollama is addressed as `host.docker.internal` from Docker Desktop.

Application services do not mount Docker's socket. Consumers have read-only filesystems where
possible, temporary scratch space and reduced capabilities. The provisioner initialises ownership
of existing catalogued model directories when needed, then drops to the non-root runtime user. It does
not recursively change ownership of unrelated files or execute arbitrary commands.

Piper is a separate GPL program, never imported by the backend. Its small launcher waits for an
installed voice before executing its unmodified server. The speech worker can wait and retry
model loading on an empty volume, while the backend serves setup immediately. Installed speech
models remain offline during normal recognition/synthesis.

On macOS, the supported speech containers use CPU inference. Native ARM64 image checks establish
compatibility evidence; physical Mac latency and memory remain separate acceptance measurements.
The cloud path has no Ollama service or local language-model requirement.

## Installation and configuration

A first-run browser flow checks resources, connects tools, installs the requested assets and
shows readiness. A native shell launcher starts Compose and opens the browser; Make is only a
developer convenience. Optional Ollama installation links and host-specific setup guidance are
provided, then the application manages requested model downloads through Ollama's API.

The provisioner receives approved model identifiers, not shell commands or arbitrary destination
paths. Its versioned catalog records sources, licence references, sizes and SHA-256 hashes. Files
are staged and checked before activation; complete valid files are reused, partial downloads can
resume, and wrong-size/hash files never become an installed model. Receipt signatures allow fast
status checks without repeatedly hashing GB-scale weights on every UI poll.

The model catalog covers Parakeet, the approved Italian Piper voice, optional Whisper and the
provisional fine-tuned Laya export. The app downloads only Laya's int8 ONNX and tokenizer. Full
training weights are published separately and are not runtime dependencies. A configured Laya
source URL locates only files matching the app's approved hashes.

Persisted installation jobs reuse the existing job runner. Interrupted jobs are queued on the
next backend start. Newly installed assets can become available without a manual container
restart. Model file verification and loading are separate states: a verified download does not
promise the inference session is already ready.

Machine configuration lives in `installation.json` and `execution-profile.json` in the data
volume; account tokens have their own directory. These are excluded from portable user-data
backups and are preserved when application data is deleted. Runtime environment variables provide
initial/advanced deployment configuration; Compose forwards only explicitly declared variables.

Fresh SQLite installations propose cloud processing and disable Whisper refinement. Existing
saved selections/databases retain their previous behaviour. Advanced external database deployments
keep the legacy defaults. Settings changes apply only while idle.

## Processing tools and failure semantics

Interviewer, analysis, evaluation and stated-limit reading are configured independently. Local
and cloud LLMs serve each role. Laya is offered only for stated-limit reading, in the default
two-step adaptive turn mode, after its model has loaded successfully. The optional TypeSafe Jev
service also reads stated limits. A separate requirement-classification choice uses the offer's
cues with the analysis model (`rules`), or Jev. The two Jev adapters share a transport client;
each fixes its own question wording and thresholds. Data sent to each tool is described in
[configuration](configuration.md#data-flow).

Availability checks distinguish configured/installed tools from absent, loading, failed or
unsigned-in tools. Local checks describe the configured Ollama model without generating or
loading it. Cloud selection requires the signed-in account's permitted plan usage. A model name
alone is not an entitlement or quality guarantee.

New work snapshots the execution plan. Legacy uniform plans are `local` or `cloud`; mixed plans
are versioned JSON strings containing the four core selections and any non-default classification
choice. A missing classification choice means `rules`; existing plans keep their stored encoding.
SQL execution-plan fields are text, with migration compatibility for older data. The UI presents
tool names, never the raw encoding.

Changes to tools, installation and sign-out require no connected/active interview or pending
background job. API mutations share the existing coordination lock. A selected provider's
unrecoverable availability/transport failure pauses the interview with saved answers; there is
no automatic provider substitution. Resume checks the selected tools again.

This is distinct from bounded transient provider retries and structured-output repair. Generated
content is validated and may be repaired under the existing policy. Speech recognition and audio
delivery have their own errors and incomplete-delivery handling; their failures do not imply
switching the LLM provider. The UI must not claim that every possible subsystem error has the
same pause behaviour.

## Preparation and interview flow

Supplied CVs, job offers and titled resources are external data, never instructions. Links in
these documents are not automatically followed. Extraction keeps provenance, and analysis output
is schema-validated before it becomes reviewable facts. The user reviews those facts and confirms
the target profession, role and seniority before approving an immutable context snapshot.

Profiles and CV checks do not depend on an interview. A profile is a named set of documents,
created on its own page, from a CV check or in the interview wizard. A CV check analyses a saved
profile or documents added for it, goes through the same review and approval, then reviews the
CV against the approved snapshot. The wizard and the CV check share the review components; the
preparation and snapshot ids in the URL hold the state of a standalone CV check.

Offer analysis extracts requirements with an obligation (`must`, `preferred` or `unclear`),
category, alternatives, equivalent routes, thresholds and links to requirements they refine.
The offer's verified wording or heading takes precedence over Jev, then the analysis model;
unclear readings defer to the next source. The review shows disagreements and lets the user
choose the obligation, overriding those readings. Structured requirements persist in the
preparation and approved snapshot. Jev heading and quantified-outcome classification have
evaluation helpers but are not connected to the application flow.

Planning builds objectives from approved context. A session keeps its configuration, execution
plan, objective state, coverage and conversation. The interviewer reacts to the latest answer,
reviewed experience and emerging relevant topics instead of consuming a fixed profession-specific
question list. Seniority represents expected responsibilities; difficulty varies the challenge
within that target.

The default adaptive turn separates a validated decision from the question implementing it. The
stated-limit reader examines the latest question/answer before that decision. The LLM remains
responsible for the interview move; Laya does not select a new objective, purpose, past experience
or hypothetical scenario. Prompt/model identities and reader provenance remain traceable.

The Laya adapter splits answer sentences using the training punctuation rule, pairs each with the
last 300 question characters, tokenizes to at most 192 tokens and applies the two-class threshold
of 0.5. The runtime uses CPU ONNX with two threads by default and idle spinning disabled. It
returns original answer sentences, which are grounded against the actual answer before use.
Classifier output does not establish correctness or competence and cannot grade the candidate.

## Voice and transcript revisions

Voice interviews use explicit turn-taking. Browser audio is converted to 16 kHz mono PCM. VAD
segments the candidate's answer for progressive live recognition; the selected interviewer then
generates its next move and Piper synthesizes delivered question text. ASR can introduce errors,
which the interview prompts and later review must account for.

Parakeet int8 serves live recognition on CPU. It has no vocabulary prompt biasing. The optional
post-call recogniser is faster-whisper large-v3-turbo with the approved vocabulary prompt, VAD
filtering, no conditioning on previous text and timestamped words. It is loaded lazily and can
be released after idle use. Live and refinement measurements from synthetic speech are not
real-recording accuracy guarantees.

Whisper second transcription is off on fresh installations. Enabling it downloads the model and
makes the post-interview pass available; existing installations preserve its previous setting.
The app does not replace it with an LLM that rewrites the recognised text. Substantive errors
spoken by the candidate must remain evidence, rather than being corrected into a better answer.

Every manual correction or retranscription creates a new answer revision; previous versions and
recordings remain available. Exports reflect the current revision. Reports record the exact
revisions they assessed, so subsequent edits do not retroactively alter an earlier report.

## Adaptive policy and public score scale

Autonomy is assessed across the whole interview using neutral probes, legitimate clarification,
assistance and graduated hints as appropriate. Counts of questions, elapsed time, ASR errors or
reasonable clarification do not automatically reduce a score. Objective coverage and time budgets
support the conversation; they are not substitutes for evidence of competence.

Assessment is separate from interviewing and uses versioned rubrics, validated structured output
and transcript-grounded quotations. Specialist correctness claims need verified supporting
evidence or explicit uncertainty. Unknown or insufficient evidence stays unassessed. Successful
schema validation does not prove that an LLM's specialist judgement is correct.

The public 0-100 score derives from descriptive anchors; it does not imply 101 reliably separable
levels of competence or predict hiring outcomes. User-visible reports distinguish the observation,
evidence, judgement and actionable feedback. Cross-profession acceptance remains an independent
gate, including tests for invented details, overextended facts and incorrectly endorsed answers.

## Persistence, jobs and recovery

SQLite is the default SQL store; PostgreSQL is supported through the same storage contracts.
SQLAlchemy adapters own persistence, with Alembic migrations. The data volume also holds document
blobs, session exports and WAV recordings. Model weights are isolated in the models volume.

Slow operations run as persisted jobs: document analysis, optional transcript refinement, reports
and installation. The runner processes one job at a time and coordinates with active interviews
so background work does not evict conversational model state or compete for inference resources.
Unfinished jobs are requeued after restart. Processing jobs keep their frozen execution plan.

Portable exports/backups record SQL rows and schema revision plus owned files. Restore supports
migration from an earlier supported schema; machine settings, account tokens and models stay
separate. Data maintenance uses the same idle/mutation coordination. Deleting user data is
separate from signing out or deleting model volumes.

Each report records the saved profile that owns it, outside its assessed content; the link
survives the profile's deletion and orders the dashboard's score lines. Deleting a CV check or a
profile removes the records only it kept. The storage adapter checks references across modules:
a snapshot stays while an interview, a report or a pending job uses it, and a document stays
while a profile, a preparation or a snapshot refers to it. Cleanup considers only the documents
of the deleted records, so uploads of work in progress are never collected.

Normal logs contain identifiers, states and timings; CV text, transcripts and audio are not logged
at INFO or higher. Optional LLM debug logs are sensitive local diagnostics and disabled by default.
No real personal data, tokens, recordings, transcripts or weights belong in git. Test fixtures are
synthetic and stored under `fixtures/synthetic/`.

## Validation and delivery

Domain logic uses unit tests, use cases use fakes, and adapters have contracts. Tests requiring
real models/GPU are marked `live` and excluded from ordinary CI. Frontend checks cover types,
Feature-Sliced boundaries, lint/format, unit tests and scripted browser acceptance. Storage
contracts also run on PostgreSQL. API schemas and generated TypeScript are checked for drift.

Runtime changes must be verified in rebuilt artifacts. Installer acceptance covers empty volumes,
cloud use without Ollama, interrupted/invalid downloads, disk shortages, model activation and
preservation of existing configuration/data. Native architecture builds and physical host tests
are reported separately. Synthetic acceptance cannot close interview-quality or real-ASR gates.

See [current status](status.md) for open acceptance work, [development](development.md) for checks,
and ADRs [0016](adr/0016-adaptive-role-based-interviews.md),
[0017](adr/0017-local-stated-limit-classifier.md), [0018](adr/0018-per-role-processing-tools.md),
[0019](adr/0019-guided-installation.md), [0020](adr/0020-faster-turns-and-reviewed-transcripts.md),
[0021](adr/0021-interface-guidance-and-navigation.md),
[0022](adr/0022-standalone-profiles-and-cv-checks.md) and
[0023](adr/0023-score-trends-per-profile.md) for the relevant decisions.
