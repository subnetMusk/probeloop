# Adaptive interview validation

> **Research and validation record.** Interpret measurements in their original conditions; they are not current runtime guarantees.
> Current operational guides: [documentation index](../README.md), [architecture](../architecture.md), and [status](../status.md).

The software-only classifier checkpoint does not establish cross-profession validity. The
adaptive policy is tested separately from legacy classifier calibration. This note records the
protocol and subsequent measurements without promoting development examples to held-out evidence.

## Design and source basis

The [OPM guide](https://www.opm.gov/policy-data-oversight/assessment-and-selection/structured-interviews/guide.pdf)
supports job analysis, stable competencies, descriptive rating anchors and probes for missing
evidence. ProbeLoop uses these principles for formative practice, without claiming that every
recruiter follows one interview format. [CIPD selection guidance](https://www.cipd.org/en/knowledge/factsheets/selection-factsheet/)
also treats selection methods as tools with different purposes and limitations.

Role level is explicit. [Civil Service behaviours](https://www.gov.uk/government/publications/success-profiles/success-profiles-civil-service-behaviours)
illustrate expectations that vary by grade. [Microsoft's guidance](https://careers.microsoft.com/v2/global/en/hiring-tips/interview-tips)
recognises clarification and reasoning as useful candidate behavior. A practice simulator must
therefore not count every request for clarification or every hint as an automatic deduction.
[Practitioner discussion](https://www.reddit.com/r/ExperiencedDevs/comments/1iuxxm7/how_do_you_help_a_struggling_interviewee/)
provides scenarios about interviewer assistance, not universal scoring labels.

Professional source cards use [HTTP semantics](https://www.rfc-editor.org/rfc/rfc9110.html#name-idempotent-methods),
[BEA price-index definitions](https://www.bea.gov/data/prices-inflation/gdp-price-index),
[BLS CPI definitions](https://www.bls.gov/cpi/questions-and-answers.htm),
[GMC professional standards](https://www.gmc-uk.org/professional-standards/the-professional-standards/good-medical-practice),
[EEF feedback guidance](https://educationendowmentfoundation.org.uk/education-evidence/guidance-reports/feedback)
and [ASQ root-cause analysis](https://asq.org/quality-resources/root-cause-analysis).
These bound scenario assumptions; they do not certify generated specialist feedback.

## Protocol

`backend/evals/fixtures/synthetic/adaptive/personas.json` separates eight development cards
(software, economics, healthcare, operations; two levels each) from four independent cards
(teaching and industrial quality; two levels each). Languages are balanced in each split.
Cards contain synthetic histories, target responsibilities, professional principles and sources,
never prewritten interview answers. `evals.adaptive_interviews` prepares confirmed contexts through
the real API and generates each response only after receiving the real app's WebSocket question.
It pauses while the test actor generates its response, preserving operational-time semantics.

`personas.v2.json` keeps the same split and adds what a 15-minute conversation needs: a private
history the actor may draw on but the application never sees, one of four answer styles
(detailed, concise and vague, confident with one mistaken belief, hesitant), and a job offer or
a resource uploaded through the document API. Three cards hold a sourced mistaken belief; the
actor receives the belief but never its correction. The actor says that it does not remember
any detail outside its CV and history, so these runs also exercise declared limits.

Preserve the persona, session, exchanges, events and model identity. Audit persona consistency,
personal references, actual elicitation, hint meaning and follow-up relevance after generation.
An automatically generated answer is not a trustworthy ground-truth label merely because its
persona was described as strong. Never use a held-out transcript to adjust a prompt and still
count it as independent acceptance evidence.

Release gates: no invented personal references, lost answers or penalties on unelicited abilities;
at least 90% relevant independent follow-ups; detection at least 80%, strong-over-weak ranking at
least 90%, zero unverified quotations; score spread at most 0.5 on the internal anchored scale
(12.5 on the public scale), measured over five regenerations of two frozen transcripts per
execution profile. Four synthetic real voice conversations cover both profiles and levels.

## Development findings

The rebuilt local economics exchange exposed a prose/numeric inconsistency: experience remained
unavailable numerically, yet a free-form recommendation asked for more practical experience.
The structural correction requires an elicited criterion on each new-policy observation and
filters unsupported prose before editorial selection. New-policy synthesis selects observation
ids only; code constructs the scope summary from actually assessed criteria. This prevents an
unconstrained summary from adding a new evaluation dimension. It is a cross-domain boundary,
not a rule about GDP terminology or a particular candidate answer.

The first tool pilot stopped at role confirmation because the driver omitted required DTO
fields. No interview was completed in that failed setup; it is not acceptance evidence.

### Direct 0–100 judgement (not adopted)

The owner asked whether criterion judgements could use every integer from 0 to 100. A temporary
judge variant scored 0–100 directly against the same descriptive anchors placed at 0, 50 and 100.
It was compared with the anchored 1–5 judge on the real economics question of session
`01a1c1bad8c57724b7dccaf81f4e53ec`: the audited strong and weak answers of
`adaptive-pair-v1`, plus a generated near-strong answer that uses the correct method but does not
state the constant-rate assumption. Five regenerations per answer, judge and execution profile
ran on the real stack (local `qwen3.5:9b`; cloud `gpt-6.1-terra`). The cloud anchored results for
the strong and weak answers are the earlier `adaptive-pair-v1` replay with the same prompt.
Raw rows, audits and logs are under the ignored `var/test-run/scale-direct-v1/`.

| Public mean (0–100) | Strong | Near-strong | Weak | Max spread |
|---|---|---|---|---|
| Local, anchored | 95.8–100 | 100 | 16.7–25 | 8.3 |
| Local, direct | 88.3–90 | 90–90.8 | 22.5–32.5 | 10.0 |
| Cloud, anchored | 95.8–100 | 91.7–95.8 | 25–29.2 | 12.5 |
| Cloud, direct | 91.8–94.7 | 87.8–91.7 | 33–39.2 | 6.2 |

Every configuration detected the weak answer's error, ranked strong above weak, produced no
unverified quotation and no correction of the strong answer. The direct scale added no
discrimination: the local judge could not separate the near-strong answer under either scale, and
the cloud judge separated it under both. The direct scale compressed both ends of the range,
reducing the strong–weak gap from about 72 to 57 public points in the cloud, and one cloud weak
accuracy score reached 25, exactly the detection threshold. The variant was therefore removed.
Reports keep anchored judgements and show integers obtained by aggregating them. One question in
one profession cannot show that a finer scale never helps; it shows no benefit in this case.

### Question-type labels and diagnostic classification

Assessment enables experience, ownership, results and reflection only for questions that ask
what the candidate actually did. The 61 recorded interviewer turns of the nine development
conversations were labelled as actual experience, hypothetical or general, or mixed. The
reference is an assistant reading of every turn, corrected by the owner on 12 reviewed turns,
nine of them chosen because the assistant and the recorded intent disagreed. The owner agreed
with the assistant on the question type in 11 of the 12. Labels, owner notes and raw classifier
outputs are under the ignored `var/test-run/` (`adaptive-label-reference-v1.json`,
`label-probe-v1/`, `laya-probe-v1/`). Agreement on the 57 turns that are not mixed:

| Source | Agreement |
|---|---|
| Local interviewer's recorded intent (`ministral-3:8b`) | 17/45 |
| Cloud interviewer's recorded intent (`gpt-6.1-terra`) | 12/12 |
| Diagnostic classifier v6, local (`qwen3.5:9b`), each question alone | 39/57 |
| Diagnostic classifier v6, cloud (`gpt-6.1-terra`), each question alone | 56/57 |
| Laya multilingual 0.4.30, zero-shot `noul` at 0.5 | 26/57 |
| Laya multilingual 0.4.30, zero-shot three-way `choice` | 36–39/57 |

All 17 local-classifier misses read technical questions about an actual past situation in the
software and economics senior cases as hypothetical, the same direction as the local
interviewer. Both classifiers treated the four mixed questions as not asking for experience.
Laya's `noul` probability stayed below 0.29 for every question, so its 0.5 decision equals always
answering no; the `choice` range depends on whether the mixed option counts as experience. This
matches the model card, which presents the checkpoints as a base to fine-tune rather than a
zero-shot decision engine. On the host CPU it loaded in 7 s and answered two questions in about
0.2 s; the same run inside Docker Desktop with weights bind-mounted from Windows did not finish
in four minutes.

The classifier does not return a question's purpose, so it cannot check hints or
clarifications. Only the cloud classifier meets a 90% agreement threshold on question type, and
the cloud interviewer already records correct types in this sample. A post-hoc agreement check
would therefore add little on either profile; the local error has to be corrected where the
question is decided. The reference is development data with only 12 owner-reviewed labels, and
the cloud classifier is the same model as the synthetic candidate.

### Single-call and two-step turns

The local interviewer's recorded question type disagreed with the reference above in 28 of 45
turns. A single-call turn chooses the objective, labels the question and writes it in one
structured generation. The two-step turn described in
[the architecture](../architecture.md#adaptive-policy-and-public-score-scale) decides and
validates first, then writes the question for the accepted decision.

Each run is five 15-minute development conversations through the real API and WebSocket:
software senior, economics junior and senior, healthcare junior and operations senior from
`personas.v2.json`. The interviewer is local (`ministral-3:8b`, 8192-token window) and the
candidate is the cloud actor (`gpt-6.1-terra`). Type agreement compares each recorded
past-experience flag with diagnostic classifier v6 on the cloud model, reading the question
alone; that classifier agreed with the reference in 56 of 57 turns. First words are timed from
the submitted answer to the first interviewer text received by the client. Sessions, summaries
and label checks are under the ignored `var/test-run/turn-compare-v1/`.

| Run | Moves | Fallbacks | Closings without fallback | Median move (s) | Median first words (s) | Probes without elicited criteria | Recorded type agrees |
|---|---|---|---|---|---|---|---|
| Single call, before the fallback fixes | 84 | 20 (24%) | 5/11 | 8.3 | not recorded | 17/56 | 37/56 |
| Two-step v1 | 88 | 26 (30%) | 0/10 | 15.4 | 9.6 | 5/61 | 60/61 |
| v2: legal objectives only, code-made closing decision | 72 | 0 | 10/10 | 10.3 | 7.1 | 3/61 | 57/61 |
| v3: stated limits read first | 86 | 5 (6%) | 9/10 | 12.1 | 8.5 | 6/70 | 69/70 |
| v4: prompt room reserved for the limits | 76 | 0 | 10/10 | 11.4 | 8.1 | 3/62 | 59/62 |
| Single call, same commit as v4 | 78 | 9 (12%) | 6/10 | 8.3 | 8.3 | 13/60 | 43/60 |

On the commit of v4 the single call fell back on 9 of 78 moves, after rejections for eight
different reasons, and its recorded type agreed with the classifier in 43 of 60 turns. Its
first words came after 8.3 s against 8.1 s for two-step. A single call also generates every
decision field before the question and releases the question only after validation, so a
separate decision adds little; reading the limits adds about one second.

In v1 most rejected decisions named an exhausted objective, a probe under another objective or
a probe after the last one the wrap-up directive allows, and the returned reason did not repair
them. A generated closing after a fallback was always rejected. Constraining decoding to the
legal objectives and letting code make the closing decision removed these fallbacks in v2. The
five v3 fallbacks were requests over the context window by up to 217 estimated tokens: the
quoted limits appear twice in a turn, while the reserved room was fixed. v4 reserves their
measured length plus a tested bound for the rest of the turn.

Writing the question after an accepted decision makes the recorded type follow the question.
In v4 the three disagreements were recorded as actual past while the question was hypothetical:
"If you had to design that presentation again", an explicit scenario, and "Looking back, what
would you have done". All three followed a stated limit. The rule not to ask for the forgotten
detail again moved the question to a hypothetical, but the decision kept its past flag, so
assessment would enable experience criteria for an answer about a hypothetical situation.

In v2 the decision reported a limit for none of the 34 answers that stated one, so the
declared-limit rule never applied. A separate reading step found 69 of the 70 answers with an
explicit limit in the recorded two-step answers, quoted three statements among the other 80
answers and took a median of 1.0 s. A variant that also classified each statement as a
forgotten detail, a missing example or a missing experience mislabelled many statements and was
not adopted. Reading limits adds about one second before the first words.

Every answer with a stated limit was read together with the next question. The automatic count
in the run summaries treats any past-experience question on the same objective as a repetition,
which overstates the problem: a forgotten figure leaves the rest of an example open to
questions. Questions that ask again for what the candidate said they do not remember were 7 to
9 of 34 in v2, 5 of 32 in v3 and 6 of 33 in v4, with four borderline cases in each of v3 and
v4. In most of them the decision's focus names the forgotten detail and the question follows it
despite the rule. Operations senior, whose actor states a limit in almost every answer,
accounts for 5 of the 11 cases in v3 and v4. The single call on the commit of v4, which reads no
limits, asked again in 9 of 34, with three borderline cases.

A narrow check of the decision's focus against the stated limits was replayed offline with the
local model on the 70 recorded v3 and v4 decisions that followed a stated limit, at a median of
0.7 s per check. It flagged 10 of the 11 audited repetitions and 6 of the 8 borderline cases,
but also 16 of the 51 other decisions, 12 of them when only past-experience or clarification
moves on the same objective are checked. Some flags are repetitions that the audit, read from
answer excerpts, missed. Most ask about the rest of an example after a forgotten figure, which
the design keeps open. Rejecting on this check would turn many ordinary probes into retries, so
it was not adopted and the remaining repetitions stay a known limitation. Replay data are under
`focus-check-v1/`.

The cloud interviewer (`gpt-6.1-terra`) ran software senior and healthcare junior in both modes
on the commit of v4:

| Cloud run | Moves | Fallbacks | Closings without fallback | Median move (s) | Median first words (s) | Probes without elicited criteria | Recorded type agrees |
|---|---|---|---|---|---|---|---|
| Single call | 34 | 11 (32%) | 2/4 | 5.9 | 4.8 | 2/21 | 21/21 |
| Two-step | 31 | 3 (10%) | 3/4 | 11.8 | 10.9 | 4/25 | 24/25 |

The cloud model records the question type correctly in both modes. Docker Desktop restarted
during a first single-call attempt, which was run again; the backend logs of the repeated run
were not kept. In the interrupted attempt the logged rejections were questions asking again for
a limit that the decision itself reported, and closings while objectives still had time. All
three two-step fallbacks were decisions that listed autonomy for a knowledge question; code now
drops autonomy when no reasoning task is elicited. On the cloud each of the three two-step calls
is a network round trip, which costs about six seconds before the first words.

Two-step is the default for both profiles. With the local model it is better on every measure
except the total move time, and the first words come no later. With the cloud model it trades
about six seconds for far fewer fixed fallback questions. `PROBELOOP_INTERVIEWER_TURN` still selects the mode for a
deployment. These runs cover five and two development cards: they choose a default and are not
acceptance evidence.

After the autonomy repair, a first cloud two-step check of software senior stopped after 13
moves, when the provider failed the simulated candidate's request three times in a row; those
moves had no fallback and their first words had a median of 20 s. The repeated check completed
both cases: 30 moves, one fallback, four closings without fallback, 24 of 25 recorded types in
agreement and no question asking again for a stated limit. The fallback followed two decisions
that gave a closing purpose to an ordinary objective while closing was not yet allowed. The
first words had a median of 14.3 s. Across the three cloud two-step runs that median ranged
from 11 to 20 s, so one run does not settle the cloud latency.

The decision schema now offers the closing purpose only while the closing objective is legal,
as it already did for objectives. Asked for a decision by a prompt that invited closing before
it was legal, the local and the cloud model each returned three decisions within the narrowed
schema. A cloud conversation of software senior with it had 16 moves, no fallback and no
rejected decision; its first words had a median of 20.7 s, so across the four cloud two-step
runs the median ranged from 11 to 21 s.

Results and release disposition are recorded in the continuation handoff as checks finish.
