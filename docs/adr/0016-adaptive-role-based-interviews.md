# 0016 — Adaptive interviews grounded in a confirmed target role

- Status: Accepted
- Date: 2026-11-09

## Context

The software-only calibration set exposed routing errors and cannot establish transfer to other
professions. Difficulty does not specify the responsibilities expected of a trainee, junior or
experienced professional. A list of topics also loses the source links and intent needed to
explain why a question was asked or a criterion assessed.

## Decision

The preparation proposes a `RoleProfile` from available documents, then requires confirmation of
profession, target role and free-text target level. Difficulty remains a separate setting.
Responsibilities and competencies describe target expectations, not verified candidate abilities.
Document-free preparations also require this profile; the new browser flow never supplies a
fictional software candidate. Nullable storage preserves older preparations and snapshots.

Plan assessment objectives, not a complete question script. Objectives keep source fact ids,
expected evidence, rubric family and priority. Generate the next question from the actual
conversation, confirmed level, remaining objectives and operational time. Keep the complete
reviewed facts in session context and select whole relevant facts for each turn.

Distinguish clarification, evidence probes, reasoning probes, graduated hints and topic changes.
Validate metadata before audio. Allow at most two partial hints for a solvable problem, without
inventing experience or providing a complete solution. Adaptive topic budgets remain subordinate
to global closing. Pauses and system latency are not performance evidence.

For the new policy, recorded question intent and elicited criteria govern assessment. A later
classifier is diagnostic, not the sole router. Preserve double judging, quote verification and
independent checking of specialist corrections. Score common autonomy once overall; legitimate
clarification and acknowledging limits can demonstrate appropriate autonomy. Never replace an
unexplored criterion with zero. Describe specialist judgements as fallible formative opinions.

Present scores on a 0–100 integer scale using the explicit affine conversion `(value - 1) * 25`
from the anchored 1–5 assessment scale. A wider presentation scale does not claim 101 reliable
measurement levels. Missing values remain unavailable. Version policy and comparability by
target expectations; keep legacy records readable.

## Validation and sources

Development conversations cover software, economics, healthcare and commercial/operations at
two levels. Teaching and industrial quality are held out for independent validation. Responses
are generated in actual conversations, then audited against primary sources. Never promote a
case used to adjust a prompt as independent evidence. Release gates include source grounding,
elicitation, assistance, persistence, at least 90% relevant held-out follow-ups, existing detection
and ranking thresholds, zero unverified quotes and repeatability checks on frozen transcripts.

The [OPM guide](https://www.opm.gov/policy-data-oversight/assessment-and-selection/structured-interviews/guide.pdf)
supports job-related competencies, anchored ratings and answer-specific probes. Its structured
selection procedure is not a prescription for every question in this practice simulator.
[Microsoft interview guidance](https://careers.microsoft.com/v2/global/en/hiring-tips/interview-tips)
encourages clarifying assumptions and explaining reasoning. The
[Civil Service behaviours](https://www.gov.uk/government/publications/success-profiles/success-profiles-civil-service-behaviours)
illustrate grade-specific expectations. The [IMF process](https://www.imf.org/en/about/careers/economist-program)
and [IMT interview guidance](https://www.imtrecruitment.org.uk/recruitment-process/interview/interview-structure-and-content)
provide distinct professional contexts, not universal hiring rules.

[Practitioner discussions](https://www.reddit.com/r/ExperiencedDevs/comments/1iuxxm7/how_do_you_help_a_struggling_interviewee/)
inform scenarios about clarification and help, but anecdotal preferences are not score labels.
Research informs development and auditing; this decision does not add automatic web retrieval
to live interviews or expand the approved milestone into live coding.
