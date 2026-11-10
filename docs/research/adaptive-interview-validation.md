# Adaptive interview validation

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

Results and release disposition are recorded in the continuation handoff as checks finish.
