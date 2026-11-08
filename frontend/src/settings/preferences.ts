import { useSyncExternalStore } from 'react'

export type Language = 'it' | 'en'
const KEY = 'probeloop.preferences'
const listeners = new Set<() => void>()

export function parseLanguage(raw: string | null): Language {
  try {
    const value: unknown = JSON.parse(raw ?? 'null')
    return value !== null &&
      typeof value === 'object' &&
      'language' in value &&
      value.language === 'en'
      ? 'en'
      : 'it'
  } catch {
    return 'it'
  }
}

let language: Language =
  typeof window === 'undefined' ? 'it' : parseLanguage(localStorage.getItem(KEY))

export function setLanguage(value: Language) {
  language = value
  localStorage.setItem(KEY, JSON.stringify({ language }))
  listeners.forEach((listener) => {
    listener()
  })
}

export function useLanguage() {
  return useSyncExternalStore(
    (listener) => {
      listeners.add(listener)
      return () => {
        listeners.delete(listener)
      }
    },
    () => language,
  )
}
