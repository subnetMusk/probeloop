import { useSyncExternalStore } from 'react'

/**
 * The preparations of CV checks started in this browser and not yet finished. A preparation
 * lives on the server, but nothing there tells a CV check from an interview, so the browser keeps
 * the list until the first review of the check exists or the user removes the entry.
 */
const KEY = 'probeloop.cv-check-preparations'
const LIMIT = 20
const listeners = new Set<() => void>()

export function parsePreparationIds(raw: string | null): string[] {
  try {
    const data: unknown = JSON.parse(raw ?? '[]')
    return Array.isArray(data)
      ? data
          .filter((id): id is string => typeof id === 'string' && /^[a-z0-9-]{1,80}$/.test(id))
          .slice(-LIMIT)
      : []
  } catch {
    return []
  }
}

function initial() {
  try {
    return parsePreparationIds(localStorage.getItem(KEY))
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
    /* Keep the list for this page when storage is unavailable. */
  }
  listeners.forEach((listener) => {
    listener()
  })
}
export function rememberCvCheckPreparation(id: string) {
  save([...ids.filter((old) => old !== id), id].slice(-LIMIT))
}
export function forgetCvCheckPreparation(id: string) {
  if (ids.includes(id)) save(ids.filter((old) => old !== id))
}
export function clearCvCheckPreparations() {
  save([])
}
export function useCvCheckPreparations() {
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
