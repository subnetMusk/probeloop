# CV review measurements

> **Research and validation record.** Interpret measurements in their original conditions; they are not current runtime guarantees.
> Current operational guides: [documentation index](../README.md), [architecture](../architecture.md), and [status](../status.md).

Measured on 2026-11-08 on machine A using `ollama:qwen3.5:9b@ctx8192`, thinking enabled,
temperature 0.1, rubric `cv.v1`. Inputs are synthetic; raw reports stay in ignored `var/test-run`.

Reproduce with the development image:

```sh
python -m evals.cv_review --output /out/cv-review.json
```

The fixture has a reversed year range, a contextual gap, a concrete recovery-time improvement,
generic API implementation detail and an unvisited portfolio link. The final smoke run took
91.82 seconds: all seven criteria had exact verified quotes, the date contradiction scored 1,
and the model requested implementation scope and decision detail. The deterministic gap check
remained informational; visual layout and link reachability remained not assessable.

The first attempt exhausted 3,500 output tokens during thinking and returned no JSON. Increasing
the output budget to 5,500, using passages of at most 3,000 characters and requesting concise
reasoning produced complete output. Long target briefs may still exceed the 8k context and fail
explicitly rather than being silently truncated. Chunk-level means can lose cross-passage context.

A subsequent run took 93.39 seconds but claimed that an unvisited link could verify skills.
The prompt now forbids that inference and URL-only evidence is removed before verification.
The final run did not repeat the claim. Exact-quote checks establish presence in the source,
not the truth of a CV statement or the semantic correctness of a judgement.

These runs establish integration and known failure handling. They do not establish ranking
validity, multilingual parity or the interview evaluator's separate calibration thresholds.

## Complete criterion output (2026-11-09)

The real-stack UI acceptance exposed a local report with 0/7 assessable criteria and eight
discarded items on the synthetic PDF CV. Replaying that approved snapshot through v1 also
exposed truncation: both attempts exhausted 5,500 output tokens after about 150 seconds each,
leaving incomplete JSON. Disabling thinking and setting presence penalty to zero completed in
37 seconds, but the list-shaped output silently omitted two criteria.

`review_cv@v2:off` therefore uses the same evidence-first, required-criterion structure as the
interview evaluator: all seven rubric keys are mandatory; each contains evidence, reason and
score in that order. Reasons and observations are bounded, thinking is off, presence penalty
is explicitly zero and the output budget is 3,500 tokens. The rubric and the source verifier
are unchanged. Rewrites still reject invented numbers; other-document and URL-only evidence
remain invalid. Existing reports retain their original prompt reference and contents.

After rebuilding the real application, the same Italian synthetic snapshots produced:

| Profile | Report | Duration | Assessable | Discarded |
|---|---|---|---|---|
| Local `qwen3.5:9b@ctx16384` | `01a1c1032ae47ffdb1c38d5223191ea1` | 46.28 s | 6/7 | 1 |
| ChatGPT `gpt-6.1-terra` | `01a1c10447b37c91917c7354c245240f` | 33.64 s | 7/7 | 0 |

Both reports were inspected in the running browser. The local consistency quotation failed
verification, so that criterion remains unavailable rather than receiving an invented score.
The earlier labelled English CV completed in 35.62 seconds with 6/7 criteria and one discarded
item; the deterministic reversed-date warning remains present, while the model's consistency
score is unavailable. This is improved functional coverage, not a CV calibration pass.

Regression checks cover required criteria, preserved rewrites, fabricated numbers, invented
quotations, wrong source identifiers and unvisited links. The full backend suite passed
(512 tests; PostgreSQL and live-model tests excluded from that invocation). Raw synthetic
measurements remain in ignored `var/test-run/m7-*` files.
