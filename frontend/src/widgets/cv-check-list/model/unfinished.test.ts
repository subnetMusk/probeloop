import { describe, expect, test } from 'vitest'

import type { CvCheckHistoryEntry, JobView, PreparationView } from '@/shared/api'
import { unfinishedChecks } from './unfinished'

const preparation = (
  id: string,
  status: string,
  createdAt: number,
  snapshotId: string | null = null,
): PreparationView =>
  ({
    id,
    status,
    created_at: createdAt,
    snapshot_id: snapshotId,
    documents: [],
  }) as unknown as PreparationView

const job = (id: string, snapshotId: string, createdAt: number, status = 'running'): JobView => ({
  id,
  kind: 'review_cv',
  subject_id: snapshotId,
  status,
  progress: 0.4,
  message: null,
  error: null,
  result: null,
  created_at: createdAt,
  started_at: createdAt,
  finished_at: null,
})

const entry = (snapshotId: string) => ({ snapshot_id: snapshotId }) as CvCheckHistoryEntry

const summary = (checks: ReturnType<typeof unfinishedChecks>['checks']) =>
  checks.map((check) =>
    check.kind === 'analysis'
      ? `analysis:${check.preparation.id}:${check.state}`
      : `review:${check.snapshotId}:${check.job ? 'running' : 'stopped'}`,
  )

describe('unfinished CV checks', () => {
  test('analyses that run, wait for review or failed stay reachable, latest first', () => {
    const { checks, finished } = unfinishedChecks({
      preparations: [
        preparation('a', 'analysing', 3),
        preparation('b', 'review', 2),
        preparation('c', 'failed', 1),
      ],
      missing: [],
      jobs: undefined,
      history: undefined,
    })
    expect(summary(checks)).toEqual([
      'analysis:a:analysing',
      'analysis:b:review',
      'analysis:c:failed',
    ])
    expect(finished).toEqual([])
  })

  test('an approved check is listed while its first review runs or after it stopped', () => {
    const { checks, finished } = unfinishedChecks({
      preparations: [preparation('a', 'approved', 1, 's1'), preparation('b', 'approved', 2, 's2')],
      missing: [],
      jobs: [job('j1', 's1', 5)],
      history: [],
    })
    expect(summary(checks)).toEqual(['review:s1:running', 'review:s2:stopped'])
    expect(finished).toEqual([])
  })

  test('a check with a version is finished, and so is a preparation the server lost', () => {
    const { checks, finished } = unfinishedChecks({
      preparations: [preparation('a', 'approved', 1, 's1')],
      missing: ['gone'],
      jobs: [],
      history: [entry('s1')],
    })
    expect(checks).toEqual([])
    expect(finished).toEqual(['gone', 'a'])
  })

  test('a new review of a checked CV keeps the check listed until it ends', () => {
    const { checks, finished } = unfinishedChecks({
      preparations: [preparation('a', 'approved', 1, 's1')],
      missing: [],
      jobs: [job('j1', 's1', 5)],
      history: [entry('s1')],
    })
    expect(summary(checks)).toEqual(['review:s1:running'])
    expect(finished).toEqual([])
  })

  test('approved preparations wait for the jobs and the history before showing or going', () => {
    const { checks, finished } = unfinishedChecks({
      preparations: [preparation('a', 'approved', 1, 's1')],
      missing: [],
      jobs: undefined,
      history: [entry('s1')],
    })
    expect(checks).toEqual([])
    expect(finished).toEqual([])
  })

  test('reviews started elsewhere are listed once, without finished or other jobs', () => {
    const other = { ...job('j3', 's9', 9), kind: 'analyse_context' }
    const { checks } = unfinishedChecks({
      preparations: [preparation('a', 'approved', 1, 's1'), preparation('b', 'approved', 2, 's1')],
      missing: [],
      jobs: [job('j1', 's1', 5), job('j2', 's2', 7), job('j4', 's4', 8, 'failed'), other],
      history: [],
    })
    expect(summary(checks)).toEqual(['review:s2:running', 'review:s1:running'])
  })
})
