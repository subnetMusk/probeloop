# 0012 — Interview evaluation pipeline: evidence-first judging without thinking

- Status: Accepted
- Date: 2026-11-08

## Context

The evaluator decision of 2026-11-07 (proposal section 9) chose `qwen3.5:9b` *with thinking*,
accuracy over speed. Its first complete report took 1,646 s for three graded answer units of a
short synthetic transcript, with nine sequential calls. A real ten-minute interview has about
ten units, so the same design would take well over an hour on machine A.

The measurements, analysed in
[docs/research/evaluation-latency.md](../research/evaluation-latency.md), show that:

- generated tokens dominate the cost, and about 87% of a judging call's output was reasoning
  that restated rules and drafted JSON; it ran out of budget before the JSON was complete;
- Ollama offers no thinking budget for this model, and prompt instructions to keep the
  reasoning short were not followed;
- thinking did not prevent the observed accuracy failure: both passes asserted the same false
  PostgreSQL correction;
- half of the observations were duplicates from the second pass and the synthesis calls;
- every judging request carried the whole snapshot, so a context of typical size would have
  overflowed the 16k window.

The approved bias mitigation (two passes with the anchors in ascending and descending order,
averaged in code) and the evidence rules (verified quotations, *not assessable*, code-owned
aggregation, versioned provenance) must stay. Prompts must stay provider-neutral: an
OpenAI-compatible adapter is planned, and wording tuned to a small local model would bias a
stronger one.

## Decision

Judge prompt v3:

- **Judging passes run without thinking** and use an evidence-first schema: for each criterion
  the quotation, then a one-sentence reason, then the score. Every rubric criterion is a
  required key. Thinking remains available through
  `PROBELOOP_EVALUATION_JUDGE_REASONING=default` and is recorded in `prompt_ref`.
- **Both anchor orders are kept for scores.** The descending pass returns scores only;
  observations and requirement coverage come from the ascending pass.
- **Each reported technical error is checked by an independent call** that sees the question,
  the answer and the reference resources but not the judge's correction. A correction is shown
  only when the check also finds the statement incorrect; otherwise it is withheld, counted as
  discarded, and the unit's accuracy score is marked unstable.
- **One synthesis call per report** selects existing observations by identifier and writes a
  short summary from score bands computed in code. It cannot add quotations or copy
  observations.
- **The approved context is compacted once** (documents once, reviewed fact statements,
  requirements with match status, area, topics) and placed first in every judging request.
- **A judge sees only its own unit's turns**, as proposal section 5.2 requires; neighbouring
  answers were observed to leak into judgements in both directions.
- **Rules the small model did not follow are enforced in code, not added to prompts**: displayed
  quotations are the transcript's own passages; technical corrections are kept only on technical
  units; the classifier decides from the questions whether a past example was asked for, and
  experience, results and reflection are *not assessable* when it was not.
- **Sampling is explicit**: the presence penalty is 0 for evaluator requests instead of the
  `qwen3.5` default of 1.5.
- **Every logical call is traced** (phase, attempts, tokens, stop reasons, duration); the job log
  records per-phase totals without text.

## Consequences

- On the labelled transcript a report takes about 2 minutes instead of 27 and passes the
  labelled checks; a ten-unit interview should take six or seven minutes, still to be measured.
- The rationale is shorter and visible in the report instead of hidden reasoning. Advice can
  still carry the model's technical misconceptions; a second call to the same model did not
  catch them, so that check was not adopted.
- Two model readings agreeing on a correction is still not verification. Corrections remain
  labelled as model judgements, and the claim check has not yet been shown to change an outcome.
- The second pass no longer contributes observations or coverage. Coverage therefore rests on one
  pass, as observations already effectively did after deduplication.
- Reports produced with v3 form new progress groups, because the prompt reference changes.
- Follow-up: persona calibration (proposal section 6) on the v3 pipeline, an Italian transcript
  in the comparison set, a real interview with an approved context, and a 12k context profile
  that may keep the whole model on the GPU.

## Alternatives considered

- **Keep thinking and raise caps** — the original workaround; it made every truncation a long
  repair and did not improve the observed accuracy.
- **A thinking budget** — not offered by Ollama for this model; cutting the reasoning stream
  leaves no JSON.
- **A smaller model or lower caps** — reduces cost by losing quality and does not address the
  duplicated work.
- **Judging several units in one call** — saves prompt processing, which is already cheap, and
  increases the cross-unit contamination observed in the first report.
- **One pass only** — removes the approved position-bias mitigation.
- **Model-specific corrective prompt wording** — the small model ignored several such rules, and
  they would bias the planned cloud provider.
- **Checking the judge's advice with the same model** — measured: it passed a wrong claim and
  withheld a plausible one.
