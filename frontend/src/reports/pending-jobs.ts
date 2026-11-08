import { useSyncExternalStore } from 'react'

const KEY = 'probeloop.report-jobs'
const listeners = new Set<() => void>()

export function parseJobs(raw: string | null): string[] {
  try {
    const data: unknown = JSON.parse(raw ?? '[]')
    return Array.isArray(data)
      ? data
          .filter((id): id is string => typeof id === 'string' && /^[a-z0-9-]{1,80}$/.test(id))
          .slice(-20)
      : []
  } catch {
    return []
  }
}

function initial() {
  try {
    return parseJobs(localStorage.getItem(KEY))
  } catch {
    return []
  }
}
let ids = initial()

function save(next: string[]) {
  ids = next
  try {
    localStorage.setItem(KEY, JSON.stringify(ids))
  } catch {
    /* Keep session notifications when storage is unavailable. */
  }
  listeners.forEach((listener) => {
    listener()
  })
}
export function rememberReportJob(id: string) {
  save([...ids.filter((old) => old !== id), id].slice(-20))
}
export function dismissReportJob(id: string) {
  save(ids.filter((old) => old !== id))
}
export function clearReportJobs() {
  save([])
}
export function useReportJobs() {
  return useSyncExternalStore(
    (listener) => {
      listeners.add(listener)
      return () => {
        listeners.delete(listener)
      }
    },
    () => ids,
  )
}
