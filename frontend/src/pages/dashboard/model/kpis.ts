import type { CvCheckHistoryEntry, InterviewHistoryEntry } from '@/shared/api'

export interface Kpis {
  /** Completed interviews. */
  interviews: number
  thisMonth: number
  /** The latest scored interview, and the change from the previous one of the same type. */
  latest: { overall: number; type: string; delta: number | null } | null
  practiceSeconds: number
  cvChecks: number
  latestCv: number | null
}

/** The headline numbers of the dashboard. Histories come newest first. */
export function kpisOf(
  interviews: readonly InterviewHistoryEntry[],
  checks: readonly CvCheckHistoryEntry[],
  now: number,
): Kpis {
  const month = new Date(now * 1000)
  const sameMonth = (at: number) => {
    const date = new Date(at * 1000)
    return date.getFullYear() === month.getFullYear() && date.getMonth() === month.getMonth()
  }
  const ended = interviews.filter((e) => e.status === 'ended')
  const scored = [...interviews]
    .sort((a, b) => b.created_at - a.created_at)
    .filter((e) => e.latest_report?.overall != null)
  const [last] = scored
  const previous =
    last &&
    scored
      .slice(1)
      .find(
        (e) =>
          e.interview_type === last.interview_type &&
          Boolean(last.latest_report?.scorer_key) &&
          e.latest_report?.scorer_key === last.latest_report?.scorer_key,
      )
  const overall = (e: InterviewHistoryEntry | undefined) => e?.latest_report?.overall ?? null
  const lastOverall = overall(last)
  const previousOverall = overall(previous)
  return {
    interviews: ended.length,
    thisMonth: ended.filter((e) => sameMonth(e.created_at)).length,
    latest:
      last && lastOverall !== null
        ? {
            overall: lastOverall,
            type: last.interview_type,
            delta:
              previousOverall === null
                ? null
                : Math.round((lastOverall - previousOverall) * 10) / 10,
          }
        : null,
    practiceSeconds: interviews.reduce((sum, e) => sum + (e.effective_s ?? 0), 0),
    cvChecks: checks.length,
    latestCv: checks[0]?.latest_report.overall ?? null,
  }
}
