import { useQueries, useQuery, useQueryClient } from '@tanstack/react-query'
import { useEffect, useRef } from 'react'

import {
  cvCheckHistoryQuery,
  forgetCvCheckPreparation,
  useCvCheckPreparations,
} from '@/entities/cv-check'
import { ApiError, api, isRunning } from '@/shared/api'
import type { CvCheckHistoryEntry, JobView, PreparationView } from '@/shared/api'

const REVIEW_JOB = 'review_cv'

/**
 * A CV check that is not finished: its documents are still analysed or wait for review
 * (`analysis`), or its approved context has no review yet or one is running (`review`).
 */
export type UnfinishedCheck =
  | {
      kind: 'analysis'
      preparation: PreparationView
      state: 'analysing' | 'review' | 'failed'
      at: number
    }
  | {
      kind: 'review'
      snapshotId: string
      preparation: PreparationView | null
      /** The running review, or null when none runs and no version exists yet. */
      job: JobView | null
      at: number
    }

/**
 * Combine the remembered preparations with the reviews running on the server. `finished` names
 * the preparations to forget: the server no longer has them, or their check has a version.
 * While the jobs or the history are loading, approved preparations are neither shown nor
 * forgotten.
 */
export function unfinishedChecks({
  preparations,
  missing,
  jobs,
  history,
}: {
  preparations: PreparationView[]
  missing: string[]
  jobs: JobView[] | undefined
  history: CvCheckHistoryEntry[] | undefined
}): { checks: UnfinishedCheck[]; finished: string[] } {
  const running = new Map<string, JobView>()
  for (const job of jobs ?? [])
    if (job.kind === REVIEW_JOB && isRunning(job)) running.set(job.subject_id, job)
  const checked = new Set(history?.map((entry) => entry.snapshot_id))
  const covered = new Set<string>()
  const checks: UnfinishedCheck[] = []
  const finished = [...missing]
  for (const preparation of preparations) {
    const snapshotId = preparation.status === 'approved' ? preparation.snapshot_id : null
    if (!snapshotId) {
      const state =
        preparation.status === 'analysing' || preparation.status === 'failed'
          ? preparation.status
          : 'review'
      checks.push({ kind: 'analysis', preparation, state, at: preparation.created_at })
      continue
    }
    if (covered.has(snapshotId) || jobs === undefined || history === undefined) continue
    const job = running.get(snapshotId) ?? null
    if (!job && checked.has(snapshotId)) {
      finished.push(preparation.id)
      continue
    }
    covered.add(snapshotId)
    checks.push({
      kind: 'review',
      snapshotId,
      preparation,
      job,
      at: job?.created_at ?? preparation.created_at,
    })
  }
  // Reviews started elsewhere: checking an existing CV again, or from an interview.
  for (const [snapshotId, job] of running)
    if (!covered.has(snapshotId))
      checks.push({ kind: 'review', snapshotId, preparation: null, job, at: job.created_at })
  checks.sort((a, b) => b.at - a.at)
  return { checks, finished }
}

/**
 * The unfinished CV checks, polled while an analysis or a review runs. Preparations whose check
 * is finished, or that the server no longer has, are forgotten.
 */
export function useUnfinishedCvChecks() {
  const client = useQueryClient()
  const ids = useCvCheckPreparations()
  const results = useQueries({
    queries: ids.map((id) => ({
      queryKey: ['preparation', id],
      queryFn: () => api.preparation(id),
      retry: (count: number, error: Error) =>
        !(error instanceof ApiError && error.status === 404) && count < 2,
      refetchInterval: (query: { state: { data?: PreparationView } }) =>
        query.state.data?.status === 'analysing' ? 1500 : false,
    })),
  })
  const jobs = useQuery({
    queryKey: ['pending-jobs'],
    queryFn: api.pendingJobs,
    refetchInterval: (query) =>
      query.state.data?.some((job) => job.kind === REVIEW_JOB) ? 1500 : false,
  })
  const history = useQuery(cvCheckHistoryQuery)

  // A review that stops running has a new version, or an error on its page.
  const reviews = (jobs.data ?? [])
    .filter((job) => job.kind === REVIEW_JOB)
    .map((job) => job.id)
    .join()
  const previous = useRef<string[]>([])
  useEffect(() => {
    const current = reviews ? reviews.split(',') : []
    if (previous.current.some((id) => !current.includes(id))) {
      void client.invalidateQueries({ queryKey: ['history'] })
      void client.invalidateQueries({ queryKey: ['cv-reviews'] })
    }
    previous.current = current
  }, [reviews, client])

  const preparations = results.flatMap((result) => (result.data ? [result.data] : []))
  const missing = ids.filter((_, index) => {
    const error = results[index]?.error
    return error instanceof ApiError && error.status === 404
  })
  const { checks, finished } = unfinishedChecks({
    preparations: preparations.toReversed(),
    missing,
    jobs: jobs.data,
    history: history.data,
  })
  const forget = finished.join()
  useEffect(() => {
    if (forget) forget.split(',').forEach(forgetCvCheckPreparation)
  }, [forget])
  return checks
}
