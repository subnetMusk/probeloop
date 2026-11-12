import { INTERVIEW_TYPES } from '@/entities/interview'
import type { ProgressGroup } from '@/shared/api'

type ApiPoint = ProgressGroup['points'][number]
export type TargetRole = NonNullable<ApiPoint['role']>

/** What changed since the previous point of the same line, without breaking it. */
export type Change = 'model' | 'prompt' | 'language' | 'role'

export interface TrendPoint {
  reportId: string
  subjectId: string
  sessionId: string | null
  createdAt: number
  overall: number
  interviewType: string | null
  profileId: string | null
  role: TargetRole | null
  rubricId: string
  rubricHash: string
  modelRef: string
  promptRef: string
  language: string
  changes: Change[]
}

export interface TrendLine {
  /** `profile:<id>` for a saved profile, else `role:<role>` or `none`. */
  key: string
  /** The saved profile, possibly deleted since. */
  profileId: string | null
  /** The role of the latest point, to name a line without a saved profile. */
  role: TargetRole | null
  /** Runs of comparable points, oldest first. */
  segments: TrendPoint[][]
}

const normalise = (text: string) => text.trim().replace(/\s+/g, ' ').toLocaleLowerCase()

/** The role as one comparable label: profession, target role and level. */
export function roleKey(role: TargetRole | null): string | null {
  if (!role) return null
  return [role.profession, role.target_role, role.seniority].map(normalise).join(' / ')
}

/** The version of each rubric family in a rubric reference such as `hr.v2+technical.v3`. */
function rubricVersions(rubricId: string): Map<string, string> {
  const versions = new Map<string, string>()
  for (const part of rubricId.split('+')) {
    const dot = part.lastIndexOf('.')
    if (dot > 0) versions.set(part.slice(0, dot), part.slice(dot + 1))
    else versions.set(part, '')
  }
  return versions
}

/**
 * Whether two reports compare (ADR 0023): only a rubric's version matters. A rubric that both
 * use must have the same version; the same reference scored with different rubric content
 * does not compare either. Other changes of evaluator are marked on the point instead.
 */
export function comparable(a: TrendPoint, b: TrendPoint): boolean {
  if (a.rubricId === b.rubricId) return a.rubricHash === b.rubricHash
  const first = rubricVersions(a.rubricId)
  for (const [family, version] of rubricVersions(b.rubricId)) {
    const other = first.get(family)
    if (other !== undefined && other !== version) return false
  }
  return true
}

function changesBetween(previous: TrendPoint | undefined, point: TrendPoint): Change[] {
  if (!previous) return []
  const changes: Change[] = []
  if (previous.modelRef !== point.modelRef) changes.push('model')
  if (previous.promptRef !== point.promptRef) changes.push('prompt')
  if (previous.language !== point.language) changes.push('language')
  if (roleKey(previous.role) !== roleKey(point.role)) changes.push('role')
  return changes
}

function keyOf(point: TrendPoint): string {
  if (point.profileId) return `profile:${point.profileId}`
  const role = roleKey(point.role)
  return role ? `role:${role}` : 'none'
}

/**
 * The overall scores of one kind of report, one line per saved profile; reports without a
 * profile share a line per target role. A line breaks only where a rubric version changes, and
 * keeps the profile's history when its documents or evaluator change. Reports without an
 * overall score are left out.
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
                profileId: p.profile_id,
                role: p.role,
                rubricId: p.rubric_id,
                rubricHash: p.rubric_hash,
                modelRef: p.model_ref,
                promptRef: p.prompt_ref,
                language: p.language,
                changes: [],
              },
            ],
      ),
    )
  const lines = new Map<string, TrendPoint[]>()
  for (const point of points) {
    const key = keyOf(point)
    lines.set(key, [...(lines.get(key) ?? []), point])
  }
  return [...lines.entries()]
    .map(([key, line]) => {
      const sorted = line.sort((a, b) => a.createdAt - b.createdAt)
      const segments: TrendPoint[][] = []
      sorted.forEach((point, index) => {
        const previous = sorted[index - 1]
        point.changes = changesBetween(previous, point)
        const run = segments.at(-1)
        if (run && previous && comparable(previous, point)) run.push(point)
        else segments.push([point])
      })
      const latest = sorted.at(-1)
      return { key, profileId: latest?.profileId ?? null, role: latest?.role ?? null, segments }
    })
    .sort((a, b) => latestAt(b) - latestAt(a))
}

const latestAt = (line: TrendLine) => line.segments.at(-1)?.at(-1)?.createdAt ?? 0

/** The interview types that have at least one scored report, in the fixed order. */
export function typesWithScores(groups: readonly ProgressGroup[]): string[] {
  const types = new Set(
    trendLines(groups, 'interview').flatMap((line) =>
      line.segments.flat().map((p) => p.interviewType),
    ),
  )
  return INTERVIEW_TYPES.filter((type) => types.has(type))
}
