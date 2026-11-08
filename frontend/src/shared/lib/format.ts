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
