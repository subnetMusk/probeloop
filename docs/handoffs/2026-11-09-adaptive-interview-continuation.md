# Adaptive interview implementation checkpoint

Date: 2026-11-09. This records implementation progress, not release acceptance.

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
