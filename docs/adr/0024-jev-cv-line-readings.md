# 0024: Jev reads CV lines under the document classification choice

- Status: Accepted
- Date: 2026-11-13
- Amends: 0020, 0022

## Context

The CV check's deterministic diagnostics found section headings and quantities with exact
patterns (`assessment/application/cv_checks.py`). The
[CV check assessment](../research/cv-check-assessment-2026-11-12.md) recorded what they miss:
letter-spaced headings, other wordings such as "Projects" or "Work history", and measures with
units outside a short list.

The Jev adapter already had wordings for both line labels. On the synthetic reference labels,
with logical lines and the line quoted in each question, the held-out CVs gave 1.00 precision and
recall for headings and 0.96 / 0.96 for quantified outcomes at threshold 0.7. The adapter marks
both tasks as evaluated, but only offer obligations were connected, through the optional
`classification` choice ([ADR 0020](0020-faster-turns-and-reviewed-transcripts.md) introduced
Jev; [ADR 0022](0022-standalone-profiles-and-cv-checks.md) the standalone CV check).

## Decision

**One choice for document lines.** The `classification` choice (`rules` or `jev`) covers offer
obligations and the CV check's line labels. With `jev`, the CV check sends every logical line of
the CV to TypeSafe before the model review, and Settings state that CV lines are sent.

**Jev reads, rules name.** Jev decides which lines are headings and which state a measured outcome
or scope. A heading counts for the experience, education or skills check when its letters, in
lower case and without spacing or punctuation, start with one of the section's words, so
"Esperienze di tirocinio" and "PROGETTI DI SVILUPPO SOFTWARE" name the experience section. With
`rules`, the exact patterns stay as they were.

**Recorded and never silent.** An information check names the models, wordings and thresholds
behind the readings. An unavailable classifier fails the CV check with its reason; it does not
fall back to the patterns.

## Consequences

- A user who already selected Jev for offer obligations now also sends CV text to TypeSafe. The
  Settings note and the data-flow table in [configuration](../configuration.md#data-flow) say so.
- The quantification check counts lines with a measure instead of matched numbers, so its counts
  are not comparable with reports made by the patterns. It is an information check and does not
  change scores.
- The measurements cover a small synthetic set. Real CVs need their own measures before these
  readings feed anything beyond the deterministic checks.
- Matching, evidence directness, scores and feedback remain with the analysis and review models.

## Alternatives considered

- **A separate choice for CV lines.** It keeps the earlier consent exact, but adds a setting for
  the same service and key; the owner chose one choice with an explicit note.
- **Falling back to the patterns when Jev fails.** It would hide which tool produced a report and
  contradicts the rule that a selected tool is never replaced without the user's action.
