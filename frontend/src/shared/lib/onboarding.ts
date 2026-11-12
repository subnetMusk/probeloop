import { useSyncExternalStore } from 'react'

/**
 * First-run marks kept in this browser: whether the guide was opened and whether the
 * "getting started" list was hidden. Losing them (private window, cleared storage) only shows
 * the list again, so failures are ignored.
 */
const GUIDE = 'probeloop.guide-seen'
const HIDDEN = 'probeloop.getting-started-hidden'
const listeners = new Set<() => void>()

function read(key: string): boolean {
  try {
    return localStorage.getItem(key) === '1'
  } catch {
    return false
  }
}

function write(key: string) {
  try {
    localStorage.setItem(key, '1')
  } catch {
    /* Remembered for this page only. */
  }
  listeners.forEach((listener) => {
    listener()
  })
}

function subscribe(listener: () => void) {
  listeners.add(listener)
  return () => {
    listeners.delete(listener)
  }
}

/** Forget the first-run marks, for example after deleting all data. */
export function resetOnboarding() {
  try {
    localStorage.removeItem(GUIDE)
    localStorage.removeItem(HIDDEN)
  } catch {
    /* Nothing stored. */
  }
  listeners.forEach((listener) => {
    listener()
  })
}

export function markGuideSeen() {
  if (!read(GUIDE)) write(GUIDE)
}

export function hideGettingStarted() {
  write(HIDDEN)
}

export function useOnboarding() {
  const guideSeen = useSyncExternalStore(
    subscribe,
    () => read(GUIDE),
    () => false,
  )
  const hidden = useSyncExternalStore(
    subscribe,
    () => read(HIDDEN),
    () => false,
  )
  return { guideSeen, hidden }
}
