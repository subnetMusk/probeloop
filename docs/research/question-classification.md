# Question classification regression measurements

Measured on 2026-11-09 with `ollama:qwen3.5:9b@ctx16384`, temperature 0.1, presence penalty 0,
thinking off. All inputs are synthetic. These small checks do not establish general accuracy.

The M6 real-stack acceptance session `01a1c0e00692795a8af436650b278198` exposed two problems:

- The final unanswered follow-up was included in the previous answer unit. That could change
  its rubric, whether a past example was requested, and the apparent depth under follow-up.
- Classification v3 called a career-motivation question hypothetical. Replaying the exact unit
  failed 10/10 times. Removing the unanswered question alone still failed 6/10 times. A grouped
  comparison had hidden this instability: 48/48 grouped classifications had been correct.

Classification v4 requests descriptive question focuses instead of abbreviated rubric kinds.
Code maps those focuses to the existing five report kinds. For nontechnical situations the
explicit past-example request determines behavioral versus hypothetical, avoiding contradictory
temporal labels. The past-example flag remains before the focus in the schema, preserving the
earlier technical-example fix. No candidate answer is sent to the classifier.

Answer-unit construction excludes questions after its last answer. The full transcript retains
them. Tests verify that neither classifier nor judges receive an unanswered follow-up.

The checked fixture is `backend/evals/fixtures/synthetic/assessment/classification.json`:
16 Italian/English cases cover career motivation, technical explanations and plans, technical
past examples, behavioral examples, hypothetical situations, logistics and an answered follow-up.

| Comparison | Rubric kinds correct | Past-example flags correct |
|---|---|---|
| Three grouped repetitions | 48/48 | 48/48 |
| Three isolated repetitions | 48/48 | 48/48 |
| Exact original session, ten repetitions after the fix | 10/10 HR | 10/10 no past example |

The evaluator stores the fixture digest, model and prompt references, every outcome and call
costs. Reproduce inside the development container:

```sh
python -m evals.classification --output /out/classification-grouped.json
python -m evals.classification --isolated --output /out/classification-isolated.json
```

The rebuilt real application generated report `01a1c11896ca7400b08ac91a62683e76` from the original
session in 48.40 seconds. It uses the HR rubric, includes only question 0 and answer 1, and has
4/4 assessable criteria. Its page was inspected in the running browser. The source speech still
has recognition errors and the off-topic answer receives low scores; these fixes do not repair
the transcript or establish judgement quality. The previous report remains unchanged.

Raw measurements and screenshots remain under ignored `var/test-run/m7-*` paths. All 15 fake
browser E2E checks passed after rebuilding, including CV and interview reports. The real
`probeloop_data` mount was restored afterwards.
