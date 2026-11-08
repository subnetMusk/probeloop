# CV review measurements

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
