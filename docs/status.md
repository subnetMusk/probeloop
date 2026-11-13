# Current implementation and acceptance status

Updated for the transcript review, preparation flow and Jev CV line checkpoint, 2026-11-13.
This page describes current behaviour; dated research and handoffs retain the measurements
available at their original checkpoints.

The [alpha.2 installation validation](research/installation-validation-2026-11-11.md) records
published-artifact checks, the empty-volume Windows run and the limits of ARM64 evidence.

## Implemented

- Reviewed document context, source-linked facts and confirmed profession, role and seniority.
- Adaptive text and voice interviews, follow-ups and per-session execution plans.
- Separate per-role processing tools in Settings, availability checks and home-page summaries.
- Local ONNX stated-limit reading with Laya, or the optional TypeSafe Jev service; interview
  decisions remain with the selected LLM.
- `auto` interviewer turns: one constrained call with ChatGPT, two steps with a local model.
- Preparation that loads and tries every engine before the first question, with visible steps.
- Optional answer reconstruction by the ChatGPT interviewer, flagged answers and a confirmation
  before reports built on live transcripts.
- Guided first run, model provisioning with hashes and progress, optional Ollama model pulls.
- Cached-file verification progress and distinct settings locks for live interviews and jobs.
- Full-width transcription switches and section navigation aligned with the visible content,
  including short trailing sections and keyboard return to the top.
- Local Parakeet recognition and Piper synthesis; optional Whisper second transcription.
- Correctable transcripts with revision history, report exports, history and portable backups;
  restoring a backup is a [documented command](operations.md#restoring-a-backup).
- One full-window transcript review that a completed call opens: chat bubbles with each turn's
  audio, doubtful words that replay their audio, in-place correction and the answers to check.
- Downloaded files named after their interview or CV check, its date and the start of its id.
- Profiles and CV checks created without an interview; a CV check can be saved as a profile or
  deleted, and deleting either keeps what interviews and other reports still use.
- Unfinished CV checks reachable from the CV checks page and its new-check notice, with their saved
  preparation state; a CV check page shows its selected report version in full and can start an
  interview on the approved context.
- Approval that confirms the target role as shown; a start without documents sets its role with
  the choice.
- Structured offer requirements with reviewable obligations, alternatives, equivalents and
  thresholds; optional Jev obligation classification, with disagreements shown for user review,
  and Jev heading and measured-outcome readings in the CV check under the same choice.
- Score trends with one line per profile, broken only by rubric version changes and marking other
  evaluator changes.
- First-run checklist, an in-app guide, localised page names and a full-screen mobile menu.
- Evidence-scoped reports with descriptive anchors shown on a 0-100 scale and unassessed criteria.
- Container-based tooling, import contracts, adapter contracts and scripted browser acceptance.
- Versioned installer packaging for amd64/arm64 images and OS-native shell launchers.

## Verified source checkpoint

The 2026-11-11 checkpoint passed container-based lint, formatting, strict type checks, import
contracts, documentation and installer checks, and API schema/type regeneration. The backend
suite passed 665 tests, with 39 skipped and 23 live tests deselected; a separate PostgreSQL 17
run passed all 39 storage contracts. The frontend passed 90 unit tests and 30 browser tests
against the rebuilt runtime, including the scripted voice interview. Two opt-in live browser
tests remained skipped. These checks do not close the real-model quality gates below.

The 2026-11-12 follow-up passed 670 backend tests (39 skipped, 23 live tests deselected),
96 frontend unit tests and 34 browser tests against a rebuilt runtime (two live tests skipped).
Container-based lint, formatting, strict type checks, import contracts, production builds and
API schema/type regeneration also passed. The earlier PostgreSQL result was not rerun because
this follow-up changes no persistence contracts.

The standalone profile and CV check checkpoint, later on 2026-11-12, passed 691 backend tests
(46 skipped, 23 live tests deselected), the 46 PostgreSQL storage contracts, 101 frontend unit
tests and 37 browser tests against a rebuilt runtime, with the two live tests skipped. One
existing browser test passed on retry after an accessibility scan ran during a button
transition. Lint, formatting, strict type checks, import contracts, documentation checks,
production builds and API schema/type regeneration also passed. A backup, delete and restore
round trip with the documented command reproduced the data summary of a local installation.

The review, flow and Jev checkpoint on 2026-11-13 passed 747 backend tests (46 skipped, 23 live
tests deselected), 120 frontend unit tests and 38 browser tests against a rebuilt runtime, with
the two live tests skipped. Lint, formatting, strict type checks, import contracts, documentation
checks and the production build also passed. The PostgreSQL contracts were not rerun because no
persistence contract changed. On one real CV, a CV check with Jev found the experience, education
and skills headings, where the exact patterns had missed the experience heading; one CV is not a
measurement.

## Remaining quality gates

- Interview behaviour and evaluator grounding across independent professions, seniority and
  difficult answers. An automated green suite is not an interviewing-quality benchmark.
- Speech-recognition accuracy and hallucination/omission behaviour on representative real
  recordings, including specialist terms and realistic microphone conditions.
- Independent stated-limit examples and real ASR transcripts. The Laya pilot used synthetic
  development data and label-derived thresholds; it is a provisional model, not a final release.
- Full CV-check calibration against the frozen reference labels and independent real documents.
  The Jev line-classifier measurements cover a small synthetic set; the heading and
  quantified-outcome readings now used by the CV check have not been measured on real CVs.
- Physical Mac latency, memory use and usability with Docker Desktop. Native ARM64 builds and
  dependency/model smoke tests establish narrower compatibility evidence, not a Mac benchmark.
- Voice preference/listening acceptance and complete real voice interviews after each relevant
  model or orchestration change.

## Reading measurements

The [Laya pilot](research/laya-limits-pilot.md) reports held-out-profession recall of 288/294
limit-containing answers and 8/312 false alarms at threshold 0.5. Those are synthetic pilot
results. The integrated adapter benchmark later measured about 261.5 ms median for its specified
multi-sentence synthetic inputs, while the earlier isolated pilot measured about 125 ms under
different conditions. Neither is the complete voice-response latency or a physical Mac result.

The provisional full checkpoint, int8 runtime export, tokenizer and model card are published at
[submsk/probeloop-laya-stated-limits](https://huggingface.co/submsk/probeloop-laya-stated-limits).
Installers pin the reviewed revision and hashes; a later fine-tuning needs its own validation and
manifest update. Laya is not adopted for choosing interview moves.

The [CV check assessment](research/cv-check-assessment-2026-11-12.md) separates the scripted
pipeline baseline from later Jev line-classification measurements. The reference labels are
frozen at version 2; classifier results do not establish matching, scoring or feedback quality
for the full CV check.

The active product work remains the adaptive interview/reporting milestone and its acceptance
work. Guided installation is an explicitly approved usability addition, and so are standalone
profiles and CV checks with the M9 history changes
([ADR 0022](adr/0022-standalone-profiles-and-cv-checks.md),
[ADR 0023](adr/0023-score-trends-per-profile.md)). Web crawling and later roadmap capabilities
are not introduced by this release.
