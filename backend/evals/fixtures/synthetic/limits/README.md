# Synthetic stated-limit sentences

Each line pairs an interviewer question with one sentence of the synthetic candidate's answer.
`stated_limit` is true when the sentence says that the candidate does not remember something or
has not had the experience asked about. Assumptions, hedges and limits of data or method are
false.

The answers come from synthetic development conversations (`personas.v2.json` and the cloud
voice interviews of 2026-11-10). Claude labelled the 606 answer contexts blind, following a
written guide; a sentence is positive when it overlaps a labelled quote. `group` is the
profession, used to hold one profession out during evaluation. See
`docs/research/laya-limits-pilot.md`.
