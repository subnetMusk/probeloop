# Audited persona calibration

Benchmark `personas@v3:technical-ownership` uses technical rubric v2. Its planted problems are
an incorrect technical claim and unclear individual contribution. The latter is measured against
`technical.ownership`, separately from practical experience. Thresholds remain detection at least
0.8, strong-over-weak ranking at least 0.9, zero unverified quotations and score spread at most 0.5
across five regenerations of the same answer.

## Inputs and audit

Generate all weak/strong answers with `--answers-only`. The default persona generator is local;
`--persona-profile cloud` uses the connected plan's interviewer model. Generation finishes before
local judging, so they do not compete for the GPU. The output records the generator and persona
prompt references, compliance attempts, exact answers and their SHA-256 digest. It contains only
synthetic data and belongs outside git.

Automatic checks verify the planted sentence, the presence or absence of "I", and digit exclusion.
They cannot prove
that a weak answer has not retracted its error, or that a strong answer is correct and establishes
individual responsibility. Review every answer against its labelled card and primary sources
before a full run. Reject or regenerate mislabelled samples; retain their original artifacts.

An audit JSON has `answers_sha256` equal to the generated digest and a `checks` list with exactly
one entry per selected card/persona pair. Each entry supplies `card`, `persona`, boolean
`label_verified: true`, nonempty `notes`, and `sources` linking the primary documentation used.
Notes should cover both the technical label and whether individual actions are identifiable.
The audit attests that review; its existence alone does not verify a technical claim.

`--answers-from` reuses the exact generated answers across local and cloud evaluators. It rejects
missing/duplicate pairs and changed questions and repeats the automatic compliance checks. The
audit must match those selected answers; changed text or unchecked labels fail before judging.
A full five-card/five-regeneration run requires that audit. Short probes can omit it but cannot
set `calibration_complete`. See the [README commands](../../README.md).

## Output and interpretation

Every review is checkpointed atomically, including its complete report, phase traces and the
partial summary. An interrupted run remains `status: running`; completed measurements set
`status: completed`. `calibration_complete` additionally requires all cards, at least five
regenerations, an accepted audit and compliant inputs. A passing short probe is not calibration.

The summary separates technical and contribution detection, ranking, quotation verification,
coverage, spread, rejected items and `corrections_on_strong`. The last field needs adjudication:
calling every correction on a requested strong persona false would assume the generator is
infallible. Missing scores stay missing; no criterion is filled to improve a metric. Selecting
a profile pins that evaluator without changing the application's default or account settings.

## Why the earlier inputs were rejected

The original November 8 index persona had passed the automatic checks, but its strong answer
described team decisions without identifying its own contribution. It also claimed that index
structures must be updated every time data changes. PostgreSQL's documented
[HOT optimization](https://www.postgresql.org/docs/current/storage-hot.html) provides cases where
new index entries are unnecessary. The cloud evaluator's correction was therefore consistent
with the source, despite the old `false_corrections` counter calling it false.

A fresh local generation also produced invalid technical detail and failed a planted-sentence
check. The first cloud generation retracted an intended wrong claim in one weak answer. Both
were rejected before full calibration. The refined persona prompt keeps the deliberate weak
belief unretracted and asks the strong persona for attributable decisions and checks. All inputs
still need review. The final source-checked corpus is generated, not hand-written.

The comparison covers five English technical topics and one persona generator. It does not
establish Italian, HR, voice or real-candidate validity, nor does agreement between two model
calls establish truth. Those limitations remain even when every numeric threshold passes.
