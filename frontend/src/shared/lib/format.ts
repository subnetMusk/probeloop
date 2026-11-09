/** `m:ss` for a number of seconds. */
export function clock(seconds: number): string {
  const whole = Math.max(0, Math.floor(seconds))
  return `${String(Math.floor(whole / 60))}:${String(whole % 60).padStart(2, '0')}`
}

/** A local date and time for an epoch timestamp in seconds. */
export function dateTime(epochSeconds: number): string {
  return new Date(epochSeconds * 1000).toLocaleString(undefined, {
    dateStyle: 'medium',
    timeStyle: 'short',
  })
}

export const INTERVIEW_TYPES: Record<string, string> = {
  technical: 'Technical',
  behavioral: 'Behavioural',
  hr: 'HR screening',
  mixed: 'Mixed',
}

export const STATUS_LABELS: Record<string, string> = {
  ready: 'Not started',
  in_progress: 'In progress',
  paused: 'Paused',
  ended: 'Ended',
  failed: 'Failed',
}

const LOCALES = { it: 'it-IT', en: 'en-GB' } as const
type Lang = keyof typeof LOCALES

/** A short date, such as "8 Nov 2026". */
export function shortDate(epochSeconds: number, language: Lang): string {
  return new Date(epochSeconds * 1000).toLocaleDateString(LOCALES[language], {
    day: 'numeric',
    month: 'short',
    year: 'numeric',
  })
}

/** "today", "3 days ago", or the date for anything older than a week. */
export function relativeDay(epochSeconds: number, language: Lang, now = Date.now() / 1000): string {
  const startOfToday = new Date(now * 1000)
  startOfToday.setHours(0, 0, 0, 0)
  const then = new Date(epochSeconds * 1000)
  then.setHours(0, 0, 0, 0)
  const days = Math.round((startOfToday.getTime() - then.getTime()) / 86_400_000)
  if (days < 0 || days > 6) return shortDate(epochSeconds, language)
  return new Intl.RelativeTimeFormat(LOCALES[language], { numeric: 'auto' }).format(-days, 'day')
}

/** A duration in whole minutes: "45 s", "9 min", "1 h 5 min". */
export function minutes(seconds: number): string {
  const whole = Math.max(0, Math.round(seconds))
  if (whole < 60) return `${String(whole)} s`
  const total = Math.round(whole / 60)
  const hours = Math.floor(total / 60)
  const rest = total % 60
  if (hours === 0) return `${String(total)} min`
  return rest ? `${String(hours)} h ${String(rest)} min` : `${String(hours)} h`
}

/** A score from 1 to 5 with one decimal, in the language's notation. */
export function score(value: number, language: Lang): string {
  return value.toLocaleString(LOCALES[language], {
    minimumFractionDigits: 1,
    maximumFractionDigits: 1,
  })
}
