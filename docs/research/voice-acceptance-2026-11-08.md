# Voice acceptance interviews, ChatGPT plan profile (2026-11-08)

> **Research and validation record.** Interpret measurements in their original conditions; they are not current runtime guarantees.
> Current operational guides: [documentation index](../README.md), [architecture](../architecture.md), and [status](../status.md).

Two complete ten-minute voice interviews ran on the real stack of machine A. The language models
used the cloud execution profile ([ADR 0013](../adr/0013-cloud-execution-profile.md)):
`chatgpt:gpt-6.1-terra` through Sign in with ChatGPT. Speech used Parakeet live, Whisper
refinement after the call, and Piper for both voices. All material is synthetic. Raw runs,
screenshots and the two mixed recordings are in the ignored `var/voice-acceptance/`,
`var/voice-candidate/` and `var/test-run/acceptance-*.wav`.

## Method

**Documents.** The synthetic material is in
`backend/evals/fixtures/synthetic/context/acceptance/`:

- a CV for a backend developer;
- two job offers, one for a payments company (getting-to-know) and one for a senior logistics
  platform role (technical);
- two project reports: a delivery-grouping project report and an event-migration exercise
  report.

They were converted to PDF and DOCX.

**Preparation.** A Playwright script drove the real Italian UI. It uploaded the files, ran the
analysis, dumped the review and approved the context.

| Interview | CV | Offer | Resources |
|---|---|---|---|
| Getting-to-know (`hr`) | PDF | PDF | project report, DOCX |
| Technical | DOCX | DOCX | project report, PDF; exercise report, DOCX |

**Interviews.** `evals/voice_candidate.py` played the candidate with a male Piper voice.

- **Answers.** Each answer was written live from the received question, never prewritten.
- **Traits.** Answers mixed several traits, logged per turn in `ground-truth.jsonl`:
  - strong first-hand answers;
  - vague ownership;
  - a generic answer;
  - admitted gaps;
  - a planted wrong technical claim;
  - a correct but subtle claim.
- **After the call.** Each interview was refined after the call, then reviewed through the API.
  Both reports were opened in the UI and exported to PDF.

## Measurements

| | Getting-to-know | Technical |
|---|---|---|
| Document analysis | 103 s, 57 facts, all with verified quotations | 83 s, 67 facts, all verified |
| Answers | 12 | 12 |
| Reply latency p50 / p95 | 3.8 s / 5.6 s | 4.2 s / 5.0 s |
| WER live / refined (against the text sent to Piper) | 8.8% / 7.7% | 13.2% / 12.3% |
| Refinement job | 168 s | 212 s |
| Report job | 146 s, 8 calls, none truncated | 162 s, 9 calls (one claim check) |
| Overall | 4.6 | 4.11 |

The requirement matrices were accurate. For the payments role, "communicates with non-technical
colleagues" and "payments domain" were *not shown*. For the senior role, deep PostgreSQL
knowledge, CI experience and Kubernetes in production were *partial*. No provider feature was
rejected: structured outputs and the reasoning setting were accepted.

## Interviewer behaviour

- It probed every planted weak answer. The vague "the team decided" answer drew "what was your
  own contribution?". The generic communication answer drew "quote a concrete message".
- It targeted the requirements the matrix marked as not shown.
- It followed the planted Kafka claim with a question on multiple partitions.
- It asked one question per turn and kept the formal register.
- Twice it said it had no information instead of inventing it (on-call compensation, on-call
  organisation).

## Report accuracy against the planted traits

| Planted trait | Report |
|---|---|
| Wrong claim: Kafka orders messages across the whole topic | Reported as a technical error with the right correction, confirmed by the claim check. The summary names it, and the unit's accuracy is 3 because a correct follow-up was in the same unit. |
| Correct but subtle claim on READ COMMITTED re-evaluating the WHERE clause | No correction; cited as a strength |
| Vague ownership (getting-to-know, turn 3) | Recognised in the reasons; ownership 4.0 for the unit, because the probed follow-up was first-hand |
| Generic answer (turn 15) | Named in the follow-up depth reason ("after a first generic answer…"); no low score |
| Shallow execution-plan answer (technical, turn 13) | Visible only indirectly (trade-offs 3, reasoning 3.5) and in an improvement note |
| Admitted gaps (payments domain; per-key ordering with a dead-letter queue) | Requirement coverage quotes the admission; improvement notes ask for detail |
| Logistics and closing | Not scored, except as noted in issue 2 |

## Issues

1. **Fixed.** The setup page said "everything runs on this computer: your voice and the
   transcript stay here" also with the cloud profile active. It now states what is sent to
   OpenAI when the ChatGPT plan profile is selected. Three setup strings were left in English
   and are now translated.
2. **Open: topic planning can mix logistics into a behavioural topic.** One planned topic
   combined payments exposure, incidents, product collaboration and expectations on hybrid work,
   on-call and pay. The salary and conditions answer therefore landed inside a scored behavioural
   unit of six answers.
3. **Open, by design: a strong follow-up masks a weak first answer.** Units are judged on all
   their follow-ups (proposal section 5.2). The planted weaknesses are named in the reasons but
   barely lower the scores. Whether recovering after a probe should cost anything is a rubric
   decision.
4. **Open: recognition of English technical terms spoken by the Italian synthetic voice.**
   Examples: "Kafka" heard as "CAF", "greedy" as "Bredi", "Grafana" as "rafana", "PostgreSQL" as
   "postre SQL". Refinement with the context vocabulary helps little: 13.2% to 12.3% WER on the
   technical interview. Part of the error is Piper's pronunciation, not the recogniser. Verified
   quotations reproduce these errors faithfully, so a transcript correction before the report
   improves them.
5. **Open: report readability in Italian.**
   - Unit kinds ("behavioral"), delivery metric names ("answer duration", "speaking rate") and
     the planner's topic descriptions are in English.
   - Each criterion shows both judges' near-identical reasons.
   - The "disagreement of at least two points" footnote appears with no flagged score.
   - The per-turn delivery list makes the page about 12,600 px long.
6. **Note.** An improvement note questioned a stated change because the approved report did not
   mention it. That is defensible but reads as a doubt about the candidate.

## Not covered

- The same interviews with the local profile after the latest changes.
- A human voice.
- A browser-driven interview: the synthetic candidate replaces the browser over the same
  WebSocket protocol.
- The CV review and the "no job offer" getting-to-know mode, which were not exercised in this
  run.
