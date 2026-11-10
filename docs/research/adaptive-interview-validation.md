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

Results and release disposition are recorded in the continuation handoff as checks finish.
