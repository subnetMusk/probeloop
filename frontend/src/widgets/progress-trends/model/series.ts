import { INTERVIEW_TYPES } from '@/entities/interview'
import type { ProgressGroup } from '@/shared/api'

export interface TrendPoint {
  reportId: string
  subjectId: string
  sessionId: string | null
  createdAt: number
  overall: number
  interviewType: string | null
  scorerKey: string
  modelRef: string
}

export interface TrendLine {
  /** The interview type, or `cv`. */
  key: string
  /** Runs of points scored the same way, oldest first. */
  segments: TrendPoint[][]
}

/**
 * The overall scores of one kind of report, one line per interview type (D1 in ADR 0014): points
 * join only when the same rubric, model, prompt and language scored them, so a change of
 * evaluator starts a new run instead of suggesting progress that the scores cannot show.
 * Reports without an overall score are left out.
 */
export function trendLines(
  groups: readonly ProgressGroup[],
  kind: 'interview' | 'cv',
  type?: string,
): TrendLine[] {
  const points = groups
    .filter((group) => group.kind === kind)
    .flatMap((group) =>
      group.points.flatMap((p): TrendPoint[] =>
        p.overall === null || (type !== undefined && p.interview_type !== type)
          ? []
          : [
              {
                reportId: p.report_id,
                subjectId: p.subject_id,
                sessionId: p.session_id,
                createdAt: p.created_at,
                overall: p.overall,
                interviewType: p.interview_type,
                scorerKey: group.scorer_key,
                modelRef: group.model_ref,
              },
            ],
      ),
    )
  const lines = new Map<string, TrendPoint[]>()
  for (const point of points) {
    const key = kind === 'cv' ? 'cv' : (point.interviewType ?? 'other')
    lines.set(key, [...(lines.get(key) ?? []), point])
  }
  const order: string[] = [...INTERVIEW_TYPES, 'other', 'cv']
  return [...lines.entries()]
    .sort(([a], [b]) => order.indexOf(a) - order.indexOf(b))
    .map(([key, line]) => {
      const segments: TrendPoint[][] = []
      for (const point of line.sort((a, b) => a.createdAt - b.createdAt)) {
        const run = segments.at(-1)
        if (run?.at(-1)?.scorerKey === point.scorerKey) run.push(point)
        else segments.push([point])
      }
      return { key, segments }
    })
}

/** The interview types that have at least one scored report, in the fixed order. */
export function typesWithScores(groups: readonly ProgressGroup[]): string[] {
  return trendLines(groups, 'interview')
    .map((line) => line.key)
    .filter((key) => key !== 'other')
}
