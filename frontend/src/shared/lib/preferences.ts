import { useSyncExternalStore } from 'react'

export type Language = 'it' | 'en'
export type Theme = 'light' | 'dark' | 'system'
export interface Preferences {
  language: Language
  volume: number
  theme: Theme
}
const KEY = 'probeloop.preferences'
const listeners = new Set<() => void>()
const DEFAULTS: Preferences = { language: 'it', volume: 1, theme: 'system' }

export function parsePreferences(raw: string | null): Preferences {
  try {
    const value: unknown = JSON.parse(raw ?? 'null')
    if (value === null || typeof value !== 'object') return { ...DEFAULTS }
    return {
      language: 'language' in value && value.language === 'en' ? 'en' : 'it',
      volume:
        'volume' in value && typeof value.volume === 'number' && Number.isFinite(value.volume)
          ? Math.max(0, Math.min(1, value.volume))
          : 1,
      theme:
        'theme' in value && (value.theme === 'dark' || value.theme === 'light')
          ? value.theme
          : 'system',
    }
  } catch {
    return { ...DEFAULTS }
  }
}
export function parseLanguage(raw: string | null): Language {
  return parsePreferences(raw).language
}
function initial() {
  try {
    return parsePreferences(localStorage.getItem(KEY))
  } catch {
    return { ...DEFAULTS }
  }
}
let preferences = initial()
export function getPreferences(): Readonly<Preferences> {
  return preferences
}

function save(update: Partial<Preferences>) {
  preferences = { ...preferences, ...update }
  try {
    localStorage.setItem(KEY, JSON.stringify(preferences))
  } catch {
    /* Preferences remain available for this session. */
  }
  listeners.forEach((listener) => {
    listener()
  })
}
export function setLanguage(language: Language) {
  save({ language })
}
export function resetPreferences() {
  preferences = { ...DEFAULTS }
  try {
    localStorage.removeItem(KEY)
  } catch {
    /* Reset the in-memory preferences as well. */
  }
  listeners.forEach((listener) => {
    listener()
  })
}
export function setTheme(theme: Theme) {
  save({ theme })
}
export function setVolume(volume: number) {
  if (Number.isFinite(volume)) save({ volume: Math.max(0, Math.min(1, volume)) })
}
export function usePreferences() {
  return useSyncExternalStore(
    (listener) => {
      listeners.add(listener)
      return () => {
        listeners.delete(listener)
      }
    },
    () => preferences,
  )
}
export function useLanguage() {
  return usePreferences().language
}

const DARK_QUERY = '(prefers-color-scheme: dark)'

function systemDark(): boolean {
  return typeof window !== 'undefined' && window.matchMedia(DARK_QUERY).matches
}

/** The theme in effect: the saved choice, or the system's when the choice is "system". */
export function useResolvedTheme(): 'light' | 'dark' {
  const { theme } = usePreferences()
  const dark = useSyncExternalStore(
    (listener) => {
      const media = window.matchMedia(DARK_QUERY)
      media.addEventListener('change', listener)
      return () => {
        media.removeEventListener('change', listener)
      }
    },
    systemDark,
    () => false,
  )
  if (theme === 'system') return dark ? 'dark' : 'light'
  return theme
}
