import { describe, expect, it } from 'vitest'

import type { CvCheckHistoryEntry, InterviewHistoryEntry } from '@/shared/api'
import { kpisOf } from './kpis'

const day = 86_400
const now = new Date(2026, 10, 20, 12).getTime() / 1000

function interview(
  id: string,
  at: number,
  type: string,
  overall: number | null,
  status = 'ended',
): InterviewHistoryEntry {
  return {
    id,
    created_at: at,
    status,
    interview_type: type,
    difficulty: 'medium',
    language: 'it',
    target_duration_s: 600,
    effective_s: status === 'ended' ? 540 : null,
    answers: 10,
    execution_profile: 'local',
    profile: null,
    snapshot_id: null,
    latest_report:
      overall === null && status !== 'ended'
        ? null
        : {
            id: `r-${id}`,
            version: 1,
            versions: 1,
            created_at: at,
            overall,
            assessed: 4,
            criteria: 5,
            language: 'it',
            model_ref: 'm',
          },
  }
}

describe('dashboard figures', () => {
  it('compares the latest score with the previous interview of the same type', () => {
    const interviews = [
      interview('a', now - day, 'technical', 4.1),
      interview('b', now - 2 * day, 'hr', 4.6),
      interview('c', now - 40 * day, 'technical', 3.6),
      interview('d', now, 'hr', null, 'in_progress'),
    ]
    const checks = [{ latest_report: { overall: 3.7 } }] as unknown as CvCheckHistoryEntry[]
    expect(kpisOf(interviews, checks, now)).toEqual({
      interviews: 3,
      thisMonth: 2,
      latest: { overall: 4.1, type: 'technical', delta: 0.5 },
      practiceSeconds: 3 * 540,
      cvChecks: 1,
      latestCv: 3.7,
    })
  })

  it('has nothing to compare at the start', () => {
    expect(kpisOf([interview('a', now, 'hr', 4)], [], now).latest).toEqual({
      overall: 4,
      type: 'hr',
      delta: null,
    })
    expect(kpisOf([], [], now)).toMatchObject({ interviews: 0, latest: null, latestCv: null })
  })
})
