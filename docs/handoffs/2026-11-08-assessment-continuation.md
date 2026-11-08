# Assessment, UI and data workflow continuation

This is a development checkpoint, not a declaration that M7, M6 or M9 is complete.
Read `AGENTS.md`, `docs/proposals/2026-11-context-evaluation-reports.md`, the CV rating
requirements, `docs/roadmap.md` and this document before continuing. Speak Italian with the
owner; repository code, comments, documentation and commit messages are English.

## Current instruction and priorities

The owner considered the evaluation latency excessive and asked for an analysis before any long
retest. That analysis and the revised pipeline, accepted by the owner, are in
[ADR 0012](../adr/0012-interview-evaluation-pipeline.md) and
[docs/research/evaluation-latency.md](../research/evaluation-latency.md). The pipeline was
measured only on the short labelled synthetic transcript; it is not calibrated. Do not run the
full persona calibration or the final voice interviews without the owner's go-ahead: both are
long. Keep prompts short and provider-neutral (an OpenAI adapter is planned): enforce rules the
small model ignores in code rather than adding corrective prompt wording.

The approved scope/order is M5, CV review, M7 assessment, M6 UI and M9 history/data management.
M8 internet enrichment is dropped. M10 live coding is outside this work. Local commits are
authorised without confirmation. Push only when the owner explicitly requests it; batch pushes,
check that CI starts, and use no PRs or AI attribution trailers.

## The 27-minute problem and the revised pipeline

The first complete evaluation took **1,646 s for three graded units** of a short synthetic text
transcript (nine sequential calls, thinking on, 9,000-token caps). It also asserted a false
PostgreSQL correction on a good answer, leaked a neighbouring answer into a unit's reason, and
duplicated half of its observations. A raw diagnostic showed about 87% of a judging call's
output was reasoning that ended in incomplete JSON. Details and numbers are in the research
note; the raw artifacts stay in ignored `var/test-run/` (`interview-review-smoke.json`,
`judge-diagnostic.json`; do not overwrite them).

Judge prompt v3 (ADR 0012), implemented and unit-tested with fakes:

- judging passes without thinking, with an evidence-first schema (quotation, reason, score) and
  every rubric criterion as a required key;
- both anchor orders still scored and averaged in code; the descending pass returns scores only;
- an independent, neutral check of each reported technical error; disagreement withholds the
  correction and marks accuracy unstable;
- one synthesis call that selects observations by id, with score bands computed in code;
- a compact approved context shared as the request prefix; judges see only their unit's turns;
- presence penalty 0 for evaluator requests (the qwen3.5 Modelfile default is 1.5);
- classification v3 (technical "how would you" questions are technical) also decides, before
  the kind, whether a past example was asked for; if not, experience, results and reflection
  are not assessable;
- technical corrections are kept only on technical units, and displayed quotations are the
  transcript's own passages;
- a per-call trace (phase, attempts, tokens, stop reasons, duration) in the eval output and
  per-phase totals in the job log; `PROBELOOP_EVALUATION_JUDGE_REASONING=default` restores
  thinking for an ablation.

Measured on machine A with the labelled transcript (see the research note for every run):
about 120 s per report instead of 1,646 s, nine or ten calls, no repairs or truncations, all
labelled checks passed. Checking the judge's advice with a second call was tried and removed:
the same model shares the same misconceptions. Wrong technical advice (for example about
`VACUUM`) and remarks about the candidate can still appear in observations. A measured
side finding: at the 16k context, 2 of 34 layers of `qwen3.5:9b` run on the CPU and generation
is about 30 tokens/s.

## Implemented code and outstanding work

### CV review

The CV review baseline was committed as `9f8fb18`, following requirements commit `679695f`.
It has seven anchored criteria, deterministic diagnostics, verified source quotes, asynchronous
jobs, immutable report versions and a report page. Practice questions feed topic planning.
Gaps and missing numerical metrics do not automatically lower scores. Visual layout and link
reachability are not assessable from extracted text. URL-only evidence is rejected.
See `docs/research/cv-review-results.md`; this is smoke coverage, not full CV calibration.

### Interview assessment and exports

- `assessment/application/{segmentation,interview_review,evidence,service}.py` and the YAML rubrics.
- Recorded follow-ups are grouped deterministically; the model classifies the question kind.
  Logistics/closing are not scored. Unknown classifications remain unscored.
- Candidate-only quotations are checked against the selected unit. A missing redundant turn
  number is resolved from the source registry; a conflicting explicit number is rejected.
- Both anchor orders must support a value; their average is computed in code. A gap of at least
  two points marks instability. Criterion aggregation uses equal available-unit weights; overall
  aggregation uses equal criterion weights and minimum evidence coverage, without imputation.
- Report requests freeze transcript revision numbers. Later corrections can generate another
  immutable version with a different fingerprint. Old CV report JSON has compatibility defaults.
- Delivery measures use recorded PCM, VAD and timing data, not an LLM. Newly captured answer
  latency starts from client-reported playback completion; older recordings may have NA latency.
- Quotes link to transcript turns and candidate audio. Notifications track jobs after navigation.
- Report exports are Markdown, JSON and WeasyPrint PDF. A custom fetcher refuses every resource
  URL, and the HTML template escapes supplied text. Pango/fonts are in the backend image.

Still needed: decisions on the first persona calibration
(`docs/research/interview-calibration.md`: thresholds missed; classification v3 fixes the
past-example decision but the calibration has not been rerun; ownership detection needs a
decision), an Italian labelled transcript, and a final visual
review of the report and PDF. The voice E2E test now covers report
generation, opening, the three downloads and regeneration with the scripted evaluator; check CI.
Technical accuracy remains a model judgement even when two calls agree.

### Settings and UI

Language, interviewer volume through a gain node, light/dark/system theme, persisted browser
preferences, report notifications and broad IT/EN translation scaffolding are implemented.
Backend problem details and failed-job messages are now localised in the UI when they are known
static messages; messages with variable parts (for example document titles) stay English. The
setup page labels the interview language explicitly. A full review of the Italian flow is
still worth doing by eye.
Settings currently focus on the preferences approved in proposal section 7; do not assume every
older, broader M6 roadmap item (provider/model/retention configuration UI or diagnostics) is done.

### History and user data

Latest report versions contribute one point per interview. Progress groups require matching
rubric content/version, model, prompt version, language and criterion IDs. Missing values remain
missing. Global report history also exposes CV reviews.

`workspace/service.py`, `storage/data.py` and `api/data_routes.py` implement structured JSON,
portable ZIP backups, empty-target CLI restore and delete-all. Backups include SQL rows, original
blobs, recordings and logs, excluding models/server configuration. ZIP preparation returns a
one-use download token, allowing the browser to stream the archive. Generated exports live in
an owned directory and are included in deletion. Restore rejects unsafe paths and nonempty
destinations. API mutation/connection guards coordinate maintenance with live sessions/jobs.

Backend roundtrips, path guards and deletion tests passed on SQLite and PostgreSQL. The README
now documents exports, backups, restore and deletion. A browser check of backup download and
delete-all on an isolated synthetic instance, and a concurrency/error-path review, remain. Never
test delete-all on the primary data volume: use isolated synthetic instances.

## Verification boundary

Historical checks before the last prompt edits included:

- 401 backend tests for the CV milestone, plus the added targeted CV guard test later.
- 85 targeted backend tests covering assessment, API and storage, including PostgreSQL.
- 29 frontend unit tests, ESLint, TypeScript, ruff, strict mypy and nine import contracts.
- M5/CV browser flows; the voice regression was rerun successfully with fakes after allowing
  completion time for transcript/audio persistence.
- A synthetic PDF was generated and visually inspected during iteration. Re-render the final
  template after any further changes; do not assume the latest template is visually accepted.

The latest prompt/pipeline edits have not had another real-model run. The newly added UI flows
have not had final rebuilt-app/E2E verification. Consult CI at the remote HEAD for checks run
after this checkpoint; CI uses fakes and does not establish model quality or runtime latency.

## Environment and commands

Workspace: `C:\Users\SOS\Desktop\git_projects\ProbeLoop`, branch `main`.
Remote: `https://github.com/subnetMusk/probeloop.git`. No PRs.

Machine A: Ryzen 9 3900X, 16 GB RAM, Docker VM about 7.7 GB, RTX 2070 Super 8 GB VRAM.
Native Ollama is reached from containers at `http://host.docker.internal:11434`.
Avoid simultaneous real inference, large builds and browser tests: memory pressure has caused
severe stalls. Do not change unrelated services, including the user's `docuum` container.

At checkpoint time the running backend still uses `compose.test.yaml` fakes and an older runtime
image. The real speech services were stopped to free memory during checks. The temporary
PostgreSQL container/network `pgtest` remains available without published ports. Recheck current
state; the running UI is not evidence of HEAD behaviour. Rebuild before verifying an artifact.

PowerShell commands, from the repository root (host source mounts are slow):

```powershell
docker compose -f compose.yaml -f compose.dev.yaml build backend
docker run --rm -v 'C:/Users/SOS/Desktop/git_projects/ProbeLoop/backend:/app' probeloop-backend:dev sh -c 'ruff check src tests evals && ruff format --check src tests evals && mypy && lint-imports && pytest -q'
docker run --rm --network pgtest -v 'C:/Users/SOS/Desktop/git_projects/ProbeLoop/backend:/app' -e PROBELOOP_TEST_DATABASE_URL=postgresql+asyncpg://probeloop@pgtest:5432/probeloop_test probeloop-backend:dev pytest -q tests/storage -k postgresql
docker run --rm --user 0 -v 'C:/Users/SOS/Desktop/git_projects/ProbeLoop/backend:/app' -v 'C:/Users/SOS/Desktop/git_projects/ProbeLoop/frontend/src/shared/api/contract:/out' probeloop-backend:dev python -m probeloop.api.contract /out
docker run --rm -v 'C:/Users/SOS/Desktop/git_projects/ProbeLoop/frontend:/work' -w /work node:24.22.0-trixie-slim sh -c 'npm run gen:types && npm run lint && npm run typecheck && npm test && npm run build'
```

Fake E2E, when appropriate:

```powershell
docker compose -f compose.yaml -f compose.test.yaml build backend
docker compose -f compose.yaml -f compose.test.yaml up -d --no-deps backend
docker run --rm --network container:probeloop-backend-1 -v 'C:/Users/SOS/Desktop/git_projects/ProbeLoop:/repo' -w /repo/frontend mcr.microsoft.com/playwright:v1.65.0-noble npx playwright test
```

Restore real engines after fake testing:

```powershell
docker compose up -d --build backend stt-worker tts-piper
```

Do not run these real-model commands immediately on taking over; first resolve the approach:

```powershell
docker run --rm -v 'C:/Users/SOS/Desktop/git_projects/ProbeLoop/backend:/app' -v 'C:/Users/SOS/Desktop/git_projects/ProbeLoop/var/test-run:/out' -e PROBELOOP_OLLAMA_BASE_URL=http://host.docker.internal:11434 probeloop-backend:dev python -m evals.interview_review --output /out/interview-review-next.json
```

For backup restore, stop the backend, mount the downloaded archive into a one-off container and
run `probeloop restore-backup /mounted/archive.zip` against an empty target. Never overwrite the
primary data to verify restore. TypeScript must remain `~5.9`; keep runtime/dependency changes
inside containers and keep real personal data, model files and runtime artifacts out of git.

## Remaining acceptance, deferred until the approach is settled

The LLM-persona calibration (`backend/evals/persona_calibration.py`, five cards in
`backend/evals/fixtures/synthetic/assessment/personas.json`) ran once on 2026-11-08; results and
open decisions are in `docs/research/interview-calibration.md`. The text regression check uses a
manually labelled synthetic transcript from
`backend/tests/fixtures/synthetic/assessment/interview.json`.
Thresholds from proposal section 6: planted-problem detection >=80%, correct persona pair
ranking >=90%, zero displayed unverified quotes, and overall spread <=0.5 across five
regenerations. Record false positives and coverage as well as headline thresholds.

The two real-stack voice interviews ran on 2026-11-08 with the ChatGPT plan profile; results and
open issues are in `docs/research/voice-acceptance-2026-11-08.md`. The original plan for them
follows, for a rerun with the local profile. It called for two real-stack voice interviews,
10 minutes each, using the same
synthetic CV: one HR/getting-to-know, one technical with a synthetic job offer. Both must go
through documents, analysis, review and approval. `evals/voice_candidate.py` already supports
`--snapshot-id` and a male candidate voice, default `it_IT-riccardo-x_low`; the interviewer is
female. Voice licensing/credits are documented in `docs/voices.md`.

Compose every final candidate answer live from the received question; never prewrite them.
Mix planted wrong technical claims, vague ownership, admitted gaps and excellent answers. Log
the trait per turn and compare report and interviewer behaviour against this ground truth.
Use the tool inbox under ignored `var/voice-candidate/run-*`. Do not also open the live interview
in a browser, and never run two calls at once. Wait for refinement/report jobs of interview 1
before interview 2.

Keep one complete mixed recording per interview at
`/data/sessions/<id>/audio/interview.wav`, copying it to ignored
`var/test-run/<interview-name>.wav`. Turn recordings remain needed for evidence playback.
Report Italian WER, latency p50/p95, probing/error handling/repetition, report accuracy,
refinement vocabulary quality, issues and the two audio paths. Finish documentation and focused
commits, and push subsequent work only on explicit request.
