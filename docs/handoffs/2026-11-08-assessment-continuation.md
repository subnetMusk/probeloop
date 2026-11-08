# Assessment, UI and data workflow continuation

This is a development checkpoint, not a declaration that M7, M6 or M9 is complete.
Read `AGENTS.md`, `docs/proposals/2026-11-context-evaluation-reports.md`, the CV rating
requirements, `docs/roadmap.md` and this document before continuing. Speak Italian with the
owner; repository code, comments, documentation and commit messages are English.

## Current instruction and priorities

The owner considers the evaluation latency excessive and asked to defer retesting for now.
Do not start by repeating a long model evaluation, a large calibration batch or the final voice
interviews. First inspect the existing measurements and design a better approach. Reduce latency
while preserving assessment quality. The latest prompt changes below are unmeasured hypotheses,
not an accepted solution. Ordinary source review and completion of the unfinished integration
can proceed without invoking real models.

The approved scope/order is M5, CV review, M7 assessment, M6 UI and M9 history/data management.
M8 internet enrichment is dropped. M10 live coding is outside this work. Local commits are
authorised without confirmation. Push only when the owner explicitly requests it; batch pushes,
check that CI starts, and use no PRs or AI attribution trailers.

## The 27-minute problem: exact evidence

The first complete interview evaluation took **1,646 seconds (27 minutes 26 seconds) to assess
four questions and four candidate answers** in a very short synthetic text transcript.
One question was a follow-up, so the four answers formed three graded answer units. An extra
candidate-question/closing exchange was present but unscored. This was report generation time,
not interview duration. It did not include speech recognition, Whisper refinement, audio
generation, CV extraction or PDF rendering. No context snapshot was supplied in this smoke run.

The draft pipeline made nine logical model calls sequentially: one classifier, two judges per
unit (six calls), and two synthesis calls. All used thinking in that draft. The structured-output
helper can add a repair attempt after invalid JSON, but per-call traces were not recorded for
the complete run, so the number and cost of repairs cannot be attributed exactly.

The evaluator was `qwen3.5:9b`, temperature 0.1, with a 16,384-token context and up to 9,000
output tokens for judging/synthesis. Output caps had been increased after shorter caps produced
empty or truncated JSON while the model spent its budget on reasoning. Increasing a cap was
a correctness workaround, not a demonstrated performance improvement.

A separate raw diagnostic at an 8,192-token context recorded:

| Measurement | Value |
|---|---|
| Input tokens | 746 |
| Generated tokens | 5,500 |
| Stop reason | length |
| Total time | 104.66 s |
| Generation time | 103.76 s |
| Generation speed | about 53 tokens/s |
| Reasoning text | 19,919 characters |
| Answer text | 2,400 characters; incomplete JSON |

The reasoning repeatedly restated rules, drafted output and checked quotations. Large amounts
of generated text and sequential calls are the main evidenced explanation. Do not blame CPU
offload or a slow GPU without measuring them. The 16k Qwen profile was observed at about
5.66 GB VRAM; the interviewer retains its separate 8k profile.

Local, ignored artifacts (same Windows workspace only):

- `var/test-run/interview-review-smoke.json`: the complete 1,646-second draft result.
- `var/test-run/judge-diagnostic.json`: raw diagnostic, including synthetic-only reasoning.
- `var/test-run/cv-review-verified.json`: separate successful CV review, 91.82 s.
- `var/test-run/synthetic-report.{json,md,pdf}` and rendered page PNGs: fake report export checks.

These artifacts are deliberately not tracked. Read the labelled fixtures to reconstruct the
inputs on another machine; do not silently overwrite the original measurements.

### Quality is also unresolved

The draft detected vague ownership and the planted claim that indexes remove the need to update
the table. However, it incorrectly criticised a good answer for saying that failed PostgreSQL
concurrent index creation can leave an invalid index. This behaviour is documented in the
[PostgreSQL CREATE INDEX reference](https://www.postgresql.org/docs/current/sql-createindex.html#SQL-CREATEINDEX-CONCURRENTLY).
That false positive affected grading as well as the suggested correction. The draft had 17
discarded model items, unstable scores and repeated synthesis observations.

Exact quote verification proves that a passage occurs in the source. It does not prove that a
technical correction, inference or CV statement is true. Preserve that distinction. A faster
version must not trade this known accuracy problem for an apparently successful latency number.

### Latest source changes, not yet measured with a real model

- `judge_unit.v2.j2` asks for one brief decision per criterion, without repeated schema drafts
  or quotation-character counting; at most two observations per judging pass.
- Both scoring passes still use thinking, opposite anchor order and a 9,000-token output cap.
- Classification now uses thinking off, capped at 1,200 output tokens.
- `synthesise.v2.j2` is intended as editorial synthesis of existing judgements, thinking off,
  capped at 2,400 tokens and four observations. It should not create new factual judgements.
- `Settings.evaluation_context_window` is 16,384; the interviewer and extraction profiles remain 8k.

Inspect the whole design rather than assuming these edits are optimal. Consider call count,
batching/context duplication, unnecessary synthesis work, reasoning behaviour and output shape.
Instrument phase times, provider attempts and token usage before selecting the smallest useful
benchmark. Preserve verified evidence, explicit not-assessable scores, versioned inputs/reports
and code-owned aggregation. Do not silently remove the approved two-pass bias mitigation or
declare a quality/performance improvement without comparative evidence.

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

Still needed: real-model quality/calibration, a measured efficient configuration, final report/UI
review, and end-to-end coverage of report generation/regeneration, navigation and downloads.
Technical accuracy and repetitive observations are known concerns, not completed acceptance.

### Settings and UI

Language, interviewer volume through a gain node, light/dark/system theme, persisted browser
preferences, report notifications and broad IT/EN translation scaffolding are implemented.
Finish remaining dynamic/untranslated strings and review the whole flow. New Playwright tests
cover keyboard volume, theme changes and axe scans, but they have not yet been run locally.
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

Backend roundtrips, path guards and deletion tests passed on SQLite and PostgreSQL. Complete UI
verification, concurrency/error-path review and documentation remain. Never test delete-all on
the primary data volume: use isolated synthetic instances.

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
docker run --rm --user 0 -v 'C:/Users/SOS/Desktop/git_projects/ProbeLoop/backend:/app' -v 'C:/Users/SOS/Desktop/git_projects/ProbeLoop/frontend/src/api/contract:/out' probeloop-backend:dev python -m probeloop.api.contract /out
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

Complete the LLM-persona calibration workflow. The five topic cards in
`backend/evals/fixtures/synthetic/assessment/personas.json` exist, but persona generation and
full calibration have not been implemented or run. The current text smoke uses a manually
labelled synthetic transcript from `backend/tests/fixtures/synthetic/assessment/interview.json`.
Thresholds from proposal section 6: planted-problem detection >=80%, correct persona pair
ranking >=90%, zero displayed unverified quotes, and overall spread <=0.5 across five
regenerations. Record false positives and coverage as well as headline thresholds.

The final acceptance remains two real-stack voice interviews, 10 minutes each, using the same
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
