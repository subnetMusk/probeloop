# Technical contribution and calibration

> **Dated design proposal.** Preserve the original rationale; consult the implemented architecture for current behaviour.
> Current operational guides: [documentation index](../README.md), [architecture](../architecture.md), and [status](../status.md).

Status: approved by the owner on 2026-11-09; implemented and verified, calibration in progress.

## Problem

The persona calibration expects vague individual contribution to receive practical experience
at most 2. Technical rubric v1 instead measures first-hand examples, choices and outcomes; it
has no separate ownership criterion. Its anchors do not justify penalising a candidate merely
for saying "we". Treating that expectation as an implementation bug would change the meaning
of the rubric without versioning it.

## Recommended decision

Add a seventh criterion, `ownership` (Individual contribution), in `technical.v2`, keeping
`technical.v1` and all historical reports immutable. Practical experience continues to describe
the concrete technical example; ownership describes how clearly the candidate attributes their
own contribution within it.

| Score | Anchor |
|---|---|
| 1 | The example leaves the candidate's own actions and contribution unclear. |
| 3 | Some own actions are identifiable, but responsibility for decisions or outcomes remains partly unclear. |
| 5 | Specific own actions, decisions and their relation to the observed outcome are clear, including the limits of the candidate's responsibility. |

Intermediate scores remain between anchors. The criterion is unavailable when no question asked
for an actual past example. Teamwork, pronouns, numbers, paid status and seniority do not earn
or lose points by themselves. Quotations must support the judgement; uncertainty concerns the
answer's evidence, never the person's ability.

Calibration then measures the vague-contribution plant against `technical.ownership`, separately
from technical accuracy. The existing detection, ranking, quotation and spread thresholds stay
unchanged. A short comparison precedes the full rerun. Because the seventh criterion changes
weights, technical v2 forms a new progress group and must be shown in report provenance.

## Alternative

Keep technical v1 unchanged. Report vague contribution as a separate diagnostic, without claiming
that experience at most 2 is required by that rubric. Retain the original failed calibration
result and its definition; publish any revised benchmark under a distinct version. This avoids
a new grading criterion but does not implement explicit ownership assessment for technical units.
