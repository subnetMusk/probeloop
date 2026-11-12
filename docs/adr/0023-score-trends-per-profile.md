# 0023: Score trends follow a profile and break only on rubric versions

- Status: Accepted
- Date: 2026-11-12
- Amends: 0013, 0016

## Context

The dashboard drew one overall-score line per interview type, and one line for CV checks. A line
started a new run whenever the scorer changed: rubric, model, prompt, language or, after
[ADR 0016](0016-adaptive-role-based-interviews.md), the confirmed target expectations. The
[UI redesign](../handoffs/2026-11-09-ui-redesign-continuation.md) recorded this as decision D1,
and [ADR 0013](0013-cloud-execution-profile.md) relied on it so that cloud and local reports were
never joined.

In use, a person practises for a role with one profile and changes tools, language or the
profile's documents along the way. Each change split the history into short runs, and editing a
profile gave the same practice a new line. The M9 roadmap item asked for comparisons valid when
the rubric version is the same, which is a weaker condition.

Reports did not record their profile before [ADR 0022](0022-standalone-profiles-and-cv-checks.md).

## Decision

**One line per profile.** Overall-score lines follow the saved profile that owns each report, so
editing the profile keeps its line. A deleted profile keeps its line, named after its last target
role. Reports without a profile share one line per target role (profession, role and level,
ignoring case and spacing). Interviews and CV checks stay in separate charts.

**Break on rubric versions only.** Two consecutive points are joined when every rubric family
used by both has the same version. The same rubric reference with different content also breaks
the line. Reports scored with different rubric families, such as an HR interview after a technical
one, are joined.

**Mark other changes.** A change of evaluator model, prompt, language or target role since the
previous point leaves the line intact. The point is drawn hollow, the tooltip names what changed,
and the table view has a note column.

The API's progress groups keep their stricter key, so criterion-by-criterion comparisons still
require the same rubric, model, prompt, language and target expectations.

## Consequences

- A profile's history reads as one line across tool and language changes. Whether such a change
  moved the score is left to the reader, who sees it marked on the point.
- A cloud report and a local report of the same profile can now be joined on the chart. This
  replaces ADR 0013's statement that they are never compared, for the overall-score chart only.
- The chart's colours follow line order instead of the interview type. The four validated chart
  colours are reused when there are more lines.
- Per-criterion trends and comparisons inside reports remain out of this decision.

## Alternatives considered

- **Keep one line per interview type**: a profile practised with several interview types would be
  split across lines.
- **Key lines by the exact target expectations**: any change of responsibilities or competencies
  would start a new line, which is the fragmentation this decision removes.
- **Join only points with the same scorer**: the previous rule.
