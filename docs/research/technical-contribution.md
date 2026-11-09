# Technical contribution verification

The owner approved a separate individual-contribution criterion on 2026-11-09, following the
[anchor proposal](../proposals/2026-11-technical-ownership-calibration.md). `technical.v2` appends
`ownership`; the six v1 criteria and their anchors are unchanged. Existing files and reports
remain immutable. New reports identify all component rubric versions and their combined hash.

The criterion is unavailable when the questions asked only for a plan. It concerns the answer's
attribution of actions and responsibility, without automatic deductions for teamwork or pronouns.
Its Italian label is "Contributo personale" in the UI and exports.

## Rebuilt application

The controlled fixture is `backend/tests/fixtures/synthetic/assessment/contribution.json`.
It contains a clear account of individual responsibility within a team, a vague team account,
and a plan-only answer. Two synthetic completed text sessions were seeded through the domain
and SQL store, then assessed through the running application's report API. These are report
integration checks, not live voice interviews or a calibration pass.

| Profile | Session | Report | Time | Clear / vague / plan contribution |
|---|---|---|---|---|
| Local | `01a1c118b6307cb59c12b9880eff08b0` | `01a1c11bc1ee7fa18bc44f9581d8c6f0` | 160.92 s | unavailable / unavailable / unavailable |
| ChatGPT plan | `01a1c119992e72cc9302128153296d66` | `01a1c11d718b7ce4b65465b2873c4c92` | 110.02 s | 5 / 1 / unavailable |

The local report discarded seven generated items. Its first two contribution scores lacked
accepted evidence; the plan was excluded by the elicitation guard. A separate local replay of
the clear answer produced two verified quotations and 5/5, demonstrating remaining variability.
The cloud report discarded nothing and distinguished all three cases as labelled. Neither
result establishes general model reliability.

Both pages were inspected in the browser. The cloud report's Markdown and JSON retain the new
criterion and rubric provenance. Its PDF was rendered with Poppler and all eleven pages were
visually checked, including the new criterion and long provenance fields. The existing local
CV report still has prompt v1, 0/7 assessed and eight rejected items after the new version was
created, confirming the previous report was not rewritten.

Regression checks preserve the six old anchors, exercise the new elicitation guard, localise
the label and verify API provenance. The full backend suite passed 517 tests; all 36 PostgreSQL
storage contracts and 15 fake browser E2E tests passed. The real backend was rebuilt afterwards,
is healthy and mounts `probeloop_data`; account settings and default execution profile were not
changed. Raw synthetic outputs and screenshots remain under ignored `var/test-run/m7-*`.
