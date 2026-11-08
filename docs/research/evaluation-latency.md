# Interview evaluation latency and accuracy

This note analyses why the first interview report took 27 minutes, describes the revised
pipeline (judge prompt v3) and records the smallest comparison that can accept or reject it.
It complements [ADR 0012](../adr/0012-interview-evaluation-pipeline.md).

## 1. Evidence before the change

All measurements are on machine A (RTX 2070 Super 8 GB, native Ollama) with `qwen3.5:9b`,
temperature 0.1 and a 16,384-token context. Raw artifacts are local and untracked
(`var/test-run/`).

### The first complete report

| Item | Value |
|---|---|
| Transcript | synthetic, English, 4 questions and 4 answers, plus an unscored closing exchange |
| Graded units | 3 (one question had a follow-up) |
| Report generation time | **1,646 s** (27 min 26 s); no audio, Whisper or CV work |
| Logical model calls | 9, sequential: 1 classification, 6 judging passes, 2 synthesis calls |
| Thinking | on for every call |
| Judging output cap | 9,000 tokens |
| Discarded model items | 17 |
| Observations in the report | 26, of which 11 are synthesis copies of judge observations |

Per-call traces were not recorded. At the measured generation speed of about 53 tokens/s,
1,646 s corresponds to roughly 87,000 generated tokens, about 9,700 per logical call. That is
more than the 9,000-token cap, which is consistent with judging calls that exhausted the cap and
then paid a full repair attempt; the split cannot be attributed exactly.

### The raw judging diagnostic

One judging request (746 prompt tokens, thinking on, 8,192 context) generated 5,500 tokens in
104.7 s and stopped at the length limit:

- 19,919 characters of reasoning, roughly 4,800 tokens: about 87% of the output;
- 2,400 characters of answer, an incomplete JSON object.

The reasoning restated the rules, drafted the JSON several times and counted quotation
characters. It did not add technical analysis. The instruction "limit internal reasoning to 600
tokens" was not followed: the model does not control its reasoning length, and Ollama exposes no
thinking budget for this model.

### Accuracy problems in the same report

- **False technical correction.** Both judging passes asserted that a failed PostgreSQL
  `CREATE INDEX CONCURRENTLY` does not leave an invalid index. The candidate was right; the
  [PostgreSQL documentation](https://www.postgresql.org/docs/current/sql-createindex.html#SQL-CREATEINDEX-CONCURRENTLY)
  describes the invalid index. The error lowered the accuracy score of a strong answer. Thinking
  was on in both passes and did not prevent it, and the second pass repeated it.
- **Cross-unit contamination.** The unit about index writes (turn 5) was scored with the reason
  "turn 7 qualifies the context": turn 7 belongs to the next unit and reached the judge through
  the surrounding turns, which included later answers.
- **Duplication.** Each pass produced its own observations, so the same correction appeared
  twice; the synthesis calls then copied observations instead of summarising them.

### A risk not visible in the smoke run

The smoke run had no approved context. With one, every judging request carried
`asdict(snapshot)`: all document texts, every fact with its quotation (which repeats the
documents), match rationales, identifiers, timestamps and hashes, plus the interviewer briefs
derived from the same facts. On a synthetic snapshot of typical size (section 4) the request
estimate exceeded the 16,384-token window together with the 9,000-token output cap, so a
realistic report would have failed with a context-overflow error before any judging.

### What the evidence says about the cost

1. Generated tokens, not prompt processing, dominate: 746 prompt tokens took 0.68 s to process;
   5,500 generated tokens took 103.8 s.
2. Most generated tokens were reasoning that neither completed the JSON nor caught the known
   technical error.
3. A third of the calls (synthesis) produced only copies.
4. Output caps had been raised to make thinking fit, which turned every truncation into a long
   repair.

CPU offload and GPU speed were not measured as causes and are not assumed.

## 2. Options considered

| Option | Effect on cost | Effect on quality | Verdict |
|---|---|---|---|
| Lower caps or a smaller model | Fewer tokens | More truncation, weaker judgements | Rejected as the main lever |
| Keep thinking, add a budget | Bounded cost | Not available for this model in Ollama; truncated reasoning gives no JSON | Not feasible |
| **Thinking off, evidence-first schema** | About 10× fewer tokens per pass | Rationale stays explicit and bounded | **Adopted** (section 5) |
| Batch several units per call | Saves prompt processing, which is cheap | More cross-unit contamination | Rejected |
| Drop the second anchor order | Halves judging | Removes the approved position-bias mitigation | Rejected |
| **Second pass returns scores only** | About a third fewer judging tokens | Mitigation applies to scores, where the bias acts; no duplicate observations | **Adopted** |
| **Synthesis selects observations by id** | One short call instead of one per two units | No copies; summary rests on verified items | **Adopted** |
| **Independent check of technical corrections** | One short call per reported error | Targets the observed false correction; never disagreed in the runs | **Adopted, benefit unproven** |
| Independent check of the judge's advice | One call per improvement or question | Same model, same knowledge gap: passed a wrong VACUUM claim | **Tried and removed** |
| **Compact context as a shared prefix** | Smaller prompts, prefix reuse by the provider | Less distracting metadata; documents still present | **Adopted** |

## 3. Revised pipeline (judge prompt v3)

For an interview with *n* scored units and *e* reported technical errors:

| Phase | Calls | Thinking | Output cap |
|---|---|---|---|
| Classification | ⌈n/8⌉ | off | 200 + 60 per unit |
| Judging, ascending anchors: scores, observations, coverage | n | off | 2,000 |
| Judging, descending anchors: scores only | n | off | 1,400 |
| Technical correction check | e (distinct quotations) | off | 500 |
| Synthesis | 1, skipped without observations | off | 800 |

Details that preserve the existing guarantees:

- **Evidence-first rationale.** Each criterion is an object whose properties come in the order
  quotation, reason, score. Ollama follows the schema's property order (ADR 0011 measured 90 of
  90), so the score is generated after the evidence and the reason. Every criterion of the
  rubric is a required key, so criteria cannot be skipped, duplicated or invented.
- **Quotes** are verified in code with the same rule as before (words compared after
  normalising case and punctuation). The stored and displayed quotation is now the transcript's
  own passage, not the model's rendering: the model added an ellipsis in 3 of 128 quotations in
  one series, which the normalised comparison accepted. Unverified scores become *not
  assessable* and are counted as discarded.
- **Both anchor orders** are still required for a score; the average and the instability flag are
  computed in code. Coverage and observations come from the ascending pass only.
- **Technical corrections.** Each statement reported as a technical error is sent to a separate
  call with a neutral prompt, the question, the full answer and any approved reference
  resources, without the judge's correction. Only a verdict of *incorrect* keeps the correction in
  the report. Any other verdict withholds it, counts it as discarded and marks the unit's
  accuracy score as unstable, because the two model readings disagree. Agreement between two
  model readings is still not a verified fact; the report keeps saying so.
- **Context.** The approved context is compacted once per review: document texts once, reviewed
  fact statements, requirements with their CV match status, the target area and the topics. It
  comes first in every judging request, so the provider can reuse the processed prefix.
  Interviewer briefs are used only when no snapshot exists.
- **Unit isolation.** A judge sees only its unit's question, follow-ups and answers, as the
  proposal's design rule requires (section 5.2: each unit is scored on its own). A draft that
  showed the two preceding turns was contaminated the other way round: the judge of the strong
  answer quoted the previous unit's wrong claim and scored accuracy 1. The quotation check
  rejected it, but the judgement itself had leaked. Follow-ups that depend on an answer are
  already grouped into the same unit.
- **Synthesis** receives the computed scores, each with a band computed in code (weak, mixed,
  strong, not assessable), and the verified observations with identifiers. It returns up to
  three priorities, up to two strengths and a short summary. The bands were added after a draft
  summary praised "strong behavioural ownership" next to an ownership score of 1. The report shows the
  summary first, with the evidence of the observations it selected, followed by the selected
  observations and the rest; nothing is copied. Unknown identifiers are discarded, and a summary
  that selects no valid observation is not shown.
- **Deterministic guards instead of prompt rules.** Prompts stay short and provider-neutral,
  because a cloud adapter is planned and wording tuned to a small local model would bias a
  stronger one. Behaviour that the small model did not follow from instructions is enforced in
  code:
  - technical corrections are kept only on technical units (one run labelled a remark about the
    candidate's honesty on a behavioural answer as a technical error, and the claim check
    confirmed it because it was asked about it as a technical statement);
  - the classifier also decides, from the questions alone, whether a unit asked for a past
    example; when none did, practical experience, results and reflection are *not assessable*.
    Without this, three of three runs scored the plan-only answer's experience at 2–2.5 even
    with an explicit instruction;
  - criterion keys, observation count and field order come from the schema.
- **Provenance.** The report's `prompt_ref` names every prompt version and the thinking choice:
  `classify_units@v3:off+judge_unit@v3:asc,desc-scores:off+check_claim@v1:off+synthesise@v3:off`.
  Progress groups keep separating reports produced by different prompt versions.
- **Instrumentation.** Every logical call records its phase, unit, attempts (repairs included),
  prompt and output tokens, stop reasons and duration. The job log receives per-phase totals
  without any text; the evaluation script stores the full trace.
- **Sampling.** Every evaluator request sets the presence penalty to 0, the default of
  OpenAI-compatible APIs. The `qwen3.5:9b` Modelfile sets 1.5, which penalises tokens already
  generated, such as a quotation repeated for several criteria. The ablation in section 5 did
  not show altered quotations, so the setting rests on the task's needs, not on a measured
  failure.
- **Classification v2** defines technical questions to include "how would you" questions about
  technical systems, and adds the past-example decision. Without thinking, a draft run
  classified the index rollout question as hypothetical, which removed its accuracy score.
  **Version 3** decides the past-example flag before the kind and states that a question that
  also asks for an explanation still asks for an example; the persona calibration showed why
  ([interview-calibration.md](interview-calibration.md), section "Follow-up").
- **Configurable thinking.** `PROBELOOP_EVALUATION_JUDGE_REASONING=default` restores thinking for
  the judging passes, with a larger cap, for the ablation in section 5.

## 4. Context size

Measured without a model on a synthetic snapshot of typical size: a 4,500-character CV, a
3,000-character job offer, two 2,500-character resources (12,500 characters of documents),
18 candidate facts, 8 requirements with matches and a 20-term vocabulary. Sizes cover the
context part of one judging request only, without instructions, rubric or turns.

| | Characters | Adapter estimate with the output cap (chars / 3 + cap) |
|---|---|---|
| Before: `asdict(snapshot)` + interviewer context | 23,348 | 16,783 tokens with a 9,000 cap: **over the 16,384 window** |
| After: compact context | 15,888 | 7,296 tokens with a 2,000 cap |

The remaining overhead above the document text is the reviewed fact statements and the
requirement list. Ollama's server log shows the shared prefix being reused between judging
calls (the cache matched the common prefix and processed only the rest of the prompt).

### GPU placement

During the comparison, `ollama ps` reported the 16k profile of `qwen3.5:9b` at 6.59 GB, of
which 5.66 GB in VRAM: 32 of 34 layers on the GPU, 805 MiB of weights on the CPU, with the
desktop holding part of the 8 GB. Generation ran at 28–30 tokens/s. The earlier diagnostic,
at an 8k context, measured about 53 tokens/s. The difference is consistent with the partial
offload at 16k, but the two runs also differ in prompt and schema, so the cause is not proven.
An 8k evaluation profile would not fit typical documents with the new budgets; a 12k profile
is a candidate to measure.

## 5. The smallest useful comparison

**Design.** The long baseline (1,646 s) was not repeated. The comparison reuses the labelled
transcript of the first report, so quality is judged against the same planted traits:

| Check | Expectation |
|---|---|
| Vague ownership (u0) | ownership ≤ 2 |
| Planted error (u4, turn 5) | reported as a technical error, and accuracy ≤ 2 |
| Correct answer naming a real failure mode (u6, turn 7) | no technical error on turn 7; accuracy ≥ 4 |
| Plan-only question (u6) | practical experience not assessable |
| Closing (u8) | not scored |
| Quotations | all verbatim in their turn; no duplicate observations |
| Stability | overall spread across repetitions |

Every run stores the per-call trace; `--debug-log` keeps the raw synthetic prompts and outputs
so that discarded items can be explained. Ablations change one setting at a time. All runs are
English; an Italian labelled transcript is still missing.

**Results on machine A** (`qwen3.5:9b`, 16k context; files in the ignored `var/test-run/`):

| Series | Runs | Seconds per report | Output tokens | Labelled checks | Notes |
|---|---|---|---|---|---|
| First report (judge v1, thinking) | 1 | 1,646 | ≈ 87,000 (estimate) | false correction on u6 | 26 observations, 11 copies |
| v3 draft, classification v1 | 1 | 121 | 2,993 | u6 classified hypothetical | summary contradicted the scores |
| v3 draft with context turns | 1 | 131 | 3,843 | u6 accuracy lost | u6 judge quoted u4's error |
| v3 before the code guards | 3 | 123–132 | 3,668–3,918 | passed, but u6 experience 2–2.5 | one "technical error" on u0 about honesty |
| v3 with code guards | 3 | 117–123 (median 120) | 3,504–3,760 | all passed, 3/3 | spread 0.13; wrong VACUUM advice in 3/3 |
| Advice check (removed) | 3 | 123–135 (median 132) | 3,772–4,078 | u6 accuracy 3.5 in one run | wrong advice passed; plausible advice withheld |
| Presence penalty 1.5 (ablation) | 1 | 110 | 3,085 | planted error not reported as a correction | 0 altered quotations; fewer observations |
| Neutral prompts without the reason length | 1 | 136 | 4,889 | all passed | reasons reached the 300-character cap |
| **Final prompts (committed)** | 2 | 110–119 (median 114) | 3,955–4,231 | **all passed, 2/2** | spread 0.03; no wrong VACUUM advice in these runs; remarks about the person remain |

Per phase, a typical v3 report spent about 63 s on the ascending passes (≈ 1,900 tokens for three
units), 45 s on the descending passes (≈ 1,400 tokens), 3 s on classification, 3 s per correction
check and 5 s on the synthesis. Every call ended with `stop`; there were no repairs. For a
ten-unit interview this extrapolates to six or seven minutes, which still has to be measured on
a real transcript with an approved context.

**Known limits that remain.**

- Advice and practice questions can carry the model's own technical misconceptions (for example
  that `VACUUM` repairs an invalid index); a second call to the same model did not catch them.
  The report labels observations as model output. Reference documents, a stronger model or the
  planned cloud adapter are the realistic remedies.
- Some observations still comment on the candidate (for example "self-reflection"); the schema
  cannot prevent it.
- The claim check confirmed the planted error every time and never disagreed with a judge, so
  its benefit on the original false positive is not demonstrated.
- One transcript, three graded units, English only: this is a regression check, not
  calibration. The first persona calibration (proposal section 6) is in
  [interview-calibration.md](interview-calibration.md); the voice acceptance interviews remain
  open.
