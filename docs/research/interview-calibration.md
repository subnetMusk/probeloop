# Interview evaluator: persona calibration, first run

Date: 2026-11-08. Machine A. Evaluator `qwen3.5:9b` (16k context), prompts
`classify_units@v2:off+judge_unit@v3:asc,desc-scores:off+check_claim@v1:off+synthesise@v3:off`
([ADR 0012](../adr/0012-interview-evaluation-pipeline.md)). Persona model `ministral-3:8b`.
Raw output is in the ignored `var/test-run/persona-calibration.*`.

## Method

`backend/evals/persona_calibration.py` implements proposal section 6.

- **Cards.** Five synthetic topic cards: PostgreSQL indexes, asyncio, mutable defaults, HTTP
  retries and transactions. Each technical question also asks for a past example the candidate
  personally handled.
- **Answers.** For each card, a weak and a strong answer are generated live.
  - The weak answer states the card's wrong claim verbatim and describes the work only as the
    team's.
  - The strong answer is correct and first-hand.
- **Trait checks in code.** The traits are checked in code, with up to three generations:
  - weak answer: the wrong claim present, no "I", no digits;
  - strong answer: "I" present, the wrong claim absent.
- **Reviews.** Each answer is reviewed five times as a one-unit interview without an approved
  context: 50 reviews.

Thresholds from the proposal:

- planted problems detected ≥ 80% (the wrong claim, and vague ownership as experience ≤ 2);
- strong ranked above weak in ≥ 90% of pairs;
- zero unverified quotations;
- overall spread ≤ 0.5.

Two fixes came from a one-card smoke test before the run.

- **Elided quotations.** A quotation joined with "..." is now verified part by part.
- **Persona trait checks.** They exclude answers in which the persona ignored its traits.

## Results

| Measure | Result | Threshold |
|---|---|---|
| Strong above weak | 15/15 usable pairs (25/25 counting the excluded answers) | ≥ 90% — met |
| Unverified quotations shown | 0 | 0 — met |
| Corrections on strong answers | 0 in 25 reviews | — |
| Wrong claim reported (correction or accuracy ≤ 2) | 20/25 weak reviews: four cards 5/5, transactions 0/5 | — |
| Planted problems, usable answers only | 10/30 (0.33) | ≥ 80% — **missed** |
| Largest spread of the mean | 0.77 (mutable defaults, weak); the other nine ≤ 0.42 | ≤ 0.5 — **missed** |
| Criteria with a score | 88.7% | — |
| Review time | median 60 s for one unit; 3,024 s for 50 reviews | — |

The asyncio and HTTP weak answers kept a first-person "I" in all three attempts and were
excluded. The evaluator still reported their wrong claims in 10 of 10 reviews.

## Findings

1. **The past-example decision is unreliable, and the code guard turns its errors into missing
   scores.** Every card asks for a past example, yet classification returned
   `past_example: false` in 27 of 50 reviews:

   | Card | False |
   |---|---|
   | asyncio | 10/10 |
   | HTTP | 10/10 |
   | mutable defaults | 3/10 |
   | transactions | 3/10 |
   | indexes | 1/10 |

   The guard added for the plan-only unit of the labelled transcript then made experience,
   results and reflection *not assessable*. That happened even for strong first-hand answers,
   for example asyncio and HTTP strong in 5 of 5 reviews. The same flips cause the only spread
   above the threshold.
2. **Vague ownership is not detected.**
   - On the compliant weak answers the judge scored practical experience 3–5. It scored 5 for
     every transactions review: "we" accounts with qualitative outcomes were read as first-hand.
   - The technical rubric has no ownership criterion, and its experience anchors do not separate
     "we" from "I". Mapping the vague-ownership plant to experience ≤ 2 may ask more of this
     rubric than it states.
   - The persona model also kept qualitative outcomes ("the system stabilized") that the trait
     checks cannot see.
3. **One wrong claim was accepted every time.** "Committing after every statement still leaves all
   previous statements in one atomic transaction that a later rollback can undo" received
   accuracy 4–5 in all five reviews. The judge called the explanation "precise". This is a
   knowledge or attention limit of the 9B model, not something a quotation check can catch.
4. **The judge never abstains.** None of the 600 criterion outputs (50 reviews, two passes, six
   criteria) was null. Every *not assessable* came from code: the past-example guard or a failed
   quotation.
5. **Requirement coverage without requirements.** Without an approved context, 47 of 50
   ascending passes still proposed one coverage item. Code discarded them, which accounts for the
   one discarded item in almost every review.
6. **What works.**
   - Ranking was perfect.
   - Quotations are always verified.
   - Strong answers never received a false correction.
   - Four of five planted claims were reported in every review.

## Limits of this run

- One persona model, which is weaker than the evaluator and only partly follows the traits.
- English only.
- One-unit interviews without an approved context or reference documents.
- Five cards.

This is a first calibration, not an acceptance.

## Follow-up: past-example classification (classification v3)

The classification request was measured alone on labelled questions. There were eight decisions
per repetition:

- each of the five cards asks for a personal example;
- in the labelled transcript, u0 asks for one, u4 asks for an explanation and u6 for a plan.

The production schema decided `kind` before `past_example`.

| Variant | Wrong decisions | Notes |
|---|---|---|
| Classification v2 (production) | 14/40, then 12/40 | asyncio and HTTP wrong every time |
| Same prompt and schema, rebuilt in the probe (control) | 12/40 | the probe reproduces production |
| `past_example` before `kind`, prompt unchanged | 0/40, then 5/80 in the final code | false negatives only |
| Field renamed to `asks_for_own_past_example` | 0/40 | |
| Definition: "even if it also asks for an explanation" | 0/40 | |
| Flag first and definition (adopted as v3) | 0/80, then 0/80 with the final wording | |

- **Unit kinds.** Every variant kept all unit kinds correct.
- **Negatives.** Explanation and plan questions were never marked as asking for an example.
- **The adopted change.** It is a schema order and one clause of the definition: no instruction
  aimed at a particular model.
- **Regression check.** On the labelled transcript, two runs of the full pipeline with v3 passed
  every check: the plan-only answer still had no experience score, the spread was 0.06 and a
  report took about 113 s.

The probe script was a one-off. Its outputs are in the ignored `var/test-run/classify-probe.jsonl`.
The persona calibration has not been rerun with v3.

## Next steps (not decided)

- **Calibration rerun.** Rerun the persona calibration with classification v3. Experience
  should then be scored where it was asked for; ownership detection is not expected to change.
- **Ownership.** Decide whether ownership belongs in the technical rubric. If it does, add an
  explicit criterion, rather than expecting experience to carry it.
- **Cloud profile.** Run the same calibration on the cloud execution profile
  ([ADR 0013](../adr/0013-cloud-execution-profile.md)) to separate model limits (finding 3) from
  pipeline design.
