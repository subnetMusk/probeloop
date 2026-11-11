# Adaptive interview implementation checkpoint

> **Historical checkpoint.** This records the state and checks at its original date. Later changes may supersede it.
> Current operational guides: [documentation index](../README.md), [architecture](../architecture.md), and [status](../status.md).

Date: 2026-11-09. This records implementation progress, not release acceptance.

## Latest active checkpoint

Core assessment/presentation is saved as `dde632a`; the evidence-first schema correction is
saved as `e2154da`. Local report v4 `01a1c1f9a1077d10883cd4603e6435a5` uses judge v6 and now has
three supported scores (100, 75, 75) with zero discarded items. Numeric unavailability remains
explicit for unelicited criteria. Requiring a quotation for every *active* criterion, even when
it explains insufficient evidence, prevents the local decoder's early empty-list shortcut.

The six remaining development cases completed in `/tmp/adaptive-development-local-v2`, copied
to `var/test-run/adaptive-development-local-v2/`. They used a separate cloud actor to avoid the
first local actor's incoherent, truncated answers. Together with the two cloud pilot cases they
cover the eight development cards and balanced languages. Do not call these independent data.
They exposed repeated demands for unavailable details and a hypothetical-to-historical drift.
The first local-actor run also had incorrect economic claims endorsed by the interviewer and
ended its third case with `llm_unavailable`; its three sessions were explicitly ended and
preserved in `adaptive-development-local-v1-ended.tar.gz`.

Current uncommitted flow changes use literal documentary quotations in the question context,
omit uncorrected model inferences while retaining all persisted facts, admit user corrections,
and ensure a real past-experience objective when documented history exists. A new internal
`answer_limit` choice is quoted against the latest answer before audio. Explicit inability to
recall/experience requires a change of evidence approach; missing context requires clarification.
It is conversation control only and never grades the candidate. All metadata must be present
before streaming speech. The normal next-question path remains one model generation.

The latest real stack image is `656e9ab...` on `probeloop_data`. A retry of the failed development
pattern is running: session `01a1c211fbe0710691bddc068576b710`, output
`/tmp/adaptive-recall-local-v3`, exec session 49149. It uses the local interviewer, cloud actor,
and realistic text answer engagement (word count / 2.4 seconds) rather than instant file answers.
Do not restart the backend before saving its `/tmp` outputs. No independent case has run yet.

Controlled calibration: `var/test-run/adaptive-pair-v1.json` contains two dynamically generated
contrasts to the same real economic question. They are matched first-question calibration,
separate from full-conversation acceptance. The source audit and exact fingerprints are in
`adaptive-pair-v1-audit.json`. Five cloud regenerations each completed: detection 100%, ranking
100%, zero unverified quotations, no corrections on the correct answer, max mean spread 0.167
on 1–5 (4.17 public points). Raw and audited results, metrics and a tar archive are preserved.
The local five-repeat run is still to do; restore these files to `/tmp` after recreations.

Latest checks: 199 targeted application/context/assessment/eval tests passed, strict mypy and
all nine import contracts passed. Earlier full checks below still need a final rerun. Rebuilt
real report pages had zero serious/critical axe violations at 1440/light, 1280/dark and 390/dark;
recorded clarification and both hints were visible. PDF exports were rendered with Poppler and
inspected. The PDF skill was used for read-only visual inspection; no external PDF was authored.

Remaining: finish/audit the retry, freeze the implementation for independent cases, run teaching
and industrial quality at two levels, audit every probe (90% gate) and invented personal refs;
finish local controlled calibration and four real voice cases. Voice services are ready. Only
Italian voices are configured, so distribute the four Italian-language voice cases across
local/cloud and junior/senior roles in different professions without changing account settings.
Then final tests, docs/roadmap and final handoff, focused local commits, real volume check.

## Earlier verification checkpoint

Implementation after `dc630df` adds profession-neutral adaptive rubrics, common autonomy counted
once, intent-based routing with diagnostic classification, guards for unelicited numeric and
prose criteria, target-aware comparability and public 0–100 values. Legacy stored JSON without
a scale remains 1–5; new JSON declares its scale and roundtrips without precision loss. The UI,
history, charts and Markdown/PDF use the same public conversion. Reports expose the confirmed
target, reference titles and recorded clarification/hints. A new-policy editorial pass selects
ids only; code builds the scope summary. Judge v5 receives only the elicited rubric subset.

Checks: 555 backend tests passed, 37 skipped and 22 live deselected before the last v5 subset
change; all 59 assessment tests and the five focused adaptive tests passed after it. All 37
PostgreSQL contracts passed on the dedicated `pgtest` database. Frontend lint/FSD/typecheck,
77 Vitest tests, Prettier and production build passed. All 15 fake browser E2Es passed (two live
tests skipped), including axe scans, target confirmation, 0–100 reports, revision regeneration
and export order. The dashboard was visually inspected at 1280/1440 in light/dark; report desktop
and mobile were inspected. The real stack is restored on `probeloop_data`.

Development findings and evidence:

- Real economics report v1 `01a1c1dbb4287dd9a0a475372224be0a` exposed unelicited experience prose.
  V2 `01a1c1e80e32728abb1097ce6e05635f` removed that dimension but returned no numeric evidence
  and exposed an empty-label summary. Both are preserved as development failures, not acceptance.
  A diagnostic confirmed that the local judge returned nulls itself, rather than a quotation
  matcher rejecting every score. V5 now receives only active criteria and separates assistance
  from the other anchors. The current rebuilt v5 report job is `01a1c1ec9c2f71fb8514d2b03187a8ee`.
- The two real cloud pilot conversations completed: software junior
  `01a1c1e833b67aa7ab2ede1ed2dd42a5`, healthcare senior
  `01a1c1e95a1f73c3bfd36fd4d7d67afa`, five dynamically generated answers each. Their persisted
  exchanges were inspected: CV-based probes, hypothetical transitions and response-based probes
  occurred without invented candidate experience. These are development cases only.
  Evidence is copied to ignored `var/test-run/pilot-cloud-v2/` and its tar archive.
- Six remaining development cards are currently running through the actual app with the local
  profile, output `/tmp/adaptive-development-local-v1` in the backend container. The driver is
  `evals.adaptive_interviews`, copied under `/tmp/evals` with `PYTHONPATH=/tmp`. Preserve outputs
  before rebuilding: Docker recreation removes `/tmp`. A base64 tar stream via `docker exec`
  retrieves these tmpfs files reliably; `docker cp` on this tmpfs was unreliable.
- `evals.adaptive_replay` requires terminal new-policy sessions and an exact SHA256 input audit
  before running repeated assessments. Its describe mode emits fingerprints only. It does not
  write reports or mutate session data. Its two guard tests pass.

Remaining acceptance: audit all development conversations and specialist facts against primary
sources; run the independent four-card set only after development fixes; require at least 90%
relevant probes and no invented personal references/data loss/unelicited penalties; frozen
five-repeat checks per execution profile, detection/ranking/evidence thresholds; four real voice
cases distributed across levels/profiles; final exports/browser inspection and final handoff.
Do not conflate the old software calibration with these gates.

## Approved scope

Implement [ADR 0016](../adr/0016-adaptive-role-based-interviews.md) within M7. Speak Italian
with the owner; repository content and commits are English. Local focused commits are allowed;
no push or PR. The owner is away and explicitly requested autonomous completion, including the
remaining work. Rebuild before runtime checks; synthetic data only; never delete or restore
over `probeloop_data`. Do not change account settings or bypass anti-bot controls.

The owner also requested a 0–100 presentation scale. The chosen conversion from anchored 1–5
scores is `(value - 1) * 25`, rounded to integers for presentation. Unavailable stays unavailable.
This does not claim more measurement precision or change the underlying descriptive anchors.

## Saved classifier checkpoint

`5fed645 Clarify technical classification and expand regression coverage` records v5, the exact
persona questions, answered closing checks and the limitations of the interrupted calibration.
47 assessment tests pass. The software-only development sample has 126/126 correct kinds and
past-example flags. Rebuilt real HR and technical reports were generated and inspected; see
[the measurements](../research/question-classification.md). Do not call this cross-domain
validation. The previous full persona runs remain interrupted and preserved.

## Role profile implementation

Saved as `4c07e6e Require a confirmed target role and level before interviews`.

The current change introduces `RoleProfile` in the plain context domain: profession, target
role, free-text seniority, expected responsibilities, competencies, basis fact ids, rationale
and confirmation. A new analysis prompt proposes it from verified facts; confirmation is
explicit and unavailable facts cannot be cited. A changed or excluded basis fact invalidates
the confirmation. Migration `0006` adds a nullable JSON column to preparations. Snapshots and
sessions keep the profile and all reviewed facts in existing JSON payloads. Legacy null profiles
remain readable. Profile changes affect snapshot identity.

The fact-review step includes role confirmation for every new preparation. A document-free
preparation is immediately reviewable with an empty profile and no demo candidate. The draft
stores unfinished role edits across Back and reloads; changing a confirmed profile blocks the
final step until it is saved again. Required fields have visible marks. Whole-fact selection
uses source links and relevance while retaining the complete facts in session context.

Checks so far:

- Ruff, strict mypy (123 sources), all nine import contracts.
- 46 context/storage checks passed, four PostgreSQL variants skipped without its URL.
- All four PostgreSQL context adapter contracts passed when enabled.
- 21 focused role/API/storage checks passed, four PostgreSQL variants skipped.
- Frontend lint, Steiger, typecheck, 74 existing tests plus the new role component test passed.
- All 15 fake browser E2E checks passed; two live checks were intentionally not enabled.
- Role form inspected at 1440/light and 1280/dark after theme transitions settled.
- The real stack was rebuilt and restored on `probeloop_data`. Real local analysis of synthetic
  CV/offer documents succeeded in preparation `01a1c191ce7f77cea13dfcbba86467b6`: it proposed a
  mid-level backend role, retained only available basis ids and required explicit confirmation.
  Approval was rejected before confirmation, then snapshot `01a1c1932dfc77cca5a52a25dfbd353a`
  retained the confirmed profile. The rebuilt real review page was inspected in the browser;
  its rationale is explicitly labelled as a model proposal requiring document verification.

Ignored evidence: `var/test-run/role-profile-*`, `checkpoint-v5-*`. Do not overwrite older
calibration artifacts. The first full backend run before updating API tests had four expected
confirmation failures (subsequently fixed) and one unrelated inbox file race in
`tests/evals/test_voice_candidate.py`; resolve that race before relying on final voice checks.

## Remaining implementation

The objective change is saved as `01d7128`. The adaptive runtime is implemented with a small
model decision schema; code derives actions, latest-answer references, hint levels and safe
criterion subsets. Unknown documentary references prevent emission. Topic engagement time
excludes pauses and model/STT/TTS delays, is persisted, and never enters scoring. The ordinary
windows are 45–240 seconds, priority weighted and subordinate to global closing; exhausted
topics also move on when generation fails. Clarification does not count as a hint or add a
scored requirement. Recorded intent includes its rubric family and preserves interrupted turns.

Verification: 117 application/domain/API/storage tests passed, 17 storage variants skipped;
all 17 PostgreSQL session contracts passed; strict mypy, nine import contracts and frontend
types passed. All 15 fake browser E2E checks passed after rebuilding. Real local economics
session `01a1c1bad8c57724b7dccaf81f4e53ec` completed four dynamically written synthetic answers,
including pause/resume, a legitimate clarification and two progressive hints (levels 1, 2).
It spoke English and recorded correct non-past intent and latest-answer ids. The first trial
exposed redundant-field and language problems; it remains in `adaptive-econ-local-v1`, while
the corrected trial is in `adaptive-econ-local-v2`. These are development cases only.

The real stack has been rebuilt/restored on `probeloop_data`. Assessment changes are now being
implemented separately; they must be rebuilt before report verification. Do not treat unused
new rubric files or partial assessment DTO changes as release acceptance.

1. Source-linked objectives are implemented and verified. The rebuilt real API created session
   `01a1c1a3a3267758bb29d47b2f3d9db5` with three model-generated objectives, supported criterion
   ids, available fact links and a closing objective. The first runtime check exercised the
   role-grounded fallback. A mixed past-example/scenario objective is valid; the later actual
   question intent must govern whether a hint is allowed. Unsupported family criteria are
   discarded without inventing a replacement. Six focused planner/policy tests and 18
   objective/API/storage checks passed (four PostgreSQL cases skipped); types were regenerated
   and typecheck passed. Role form column heights were aligned and its real page rechecked.
   After clarifying priority semantics, real local session `01a1c1a57e9b7d1fb3fd80746b0f8210`
   generated junior-economist objectives without a CV: real/nominal measures, uncertainty and
   constrained economic reasoning. All documentary reference lists were empty, as required.
   This is a development smoke check, not independent transfer validation.
2. Plan source-linked assessment objectives and govern turn intent, transcript-grounded emerging
   topics, role-appropriate depth, at most two hints, and adaptive topic budgets. Validate all
   essential metadata before audio. Keep the normal path to one model generation per turn.
3. Use recorded elicitation for new-policy assessment; classifier becomes diagnostic. Version
   profession-neutral rubrics and common autonomy (one aggregate criterion), guard unelicited
   criteria, preserve two passes and evidence/correction checks, record assistance and target
   expectations in reports, separate progress comparisons by target/policy.
4. Implement 0–100 presentation consistently in UI, charts, Markdown/PDF/JSON presentation
   metadata and shared parity tests without silently changing legacy raw score meaning.
5. Cross-profession development conversations: software, economics, healthcare, commercial/
   operations at two levels and balanced languages. Teaching and industrial quality stay held
   out. Responses must be produced during actual conversations, with audited source labels.
   Gates: no invented personal references, no data loss or unelicited penalties; at least 90%
   relevant held-out follow-ups; retain detection/ranking/evidence thresholds; two frozen
   transcripts, five regenerations per execution profile; four synthetic voice checks.
6. Components/axe, final SQLite/PostgreSQL/frontend/E2E checks, exports and legacy compatibility,
   README/roadmap/architecture/final handoff. Restore the real stack and inspect its mount.

Research is continuous: primary sources for facts and scoring principles, forums as anecdotes.
Additional source leads verified during this implementation are EEF feedback guidance, ASQ root
cause analysis, and Federal Reserve real-versus-nominal GDP explanations. Do not use any held-out
conversation to tune a prompt and then count it as independent acceptance evidence.
