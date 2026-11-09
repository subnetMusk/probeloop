import { defineMessages } from '@/shared/i18n'

export const INTERVIEW_TYPES = ['technical', 'behavioral', 'hr', 'mixed'] as const
export type InterviewType = (typeof INTERVIEW_TYPES)[number]

/** The chart colour of each interview type: fixed, so a filter never repaints a series. */
export const TYPE_COLORS: Record<InterviewType, string> = {
  technical: 'var(--chart-1)',
  behavioral: 'var(--chart-2)',
  hr: 'var(--chart-3)',
  mixed: 'var(--chart-4)',
}

export const interviewLabels = defineMessages({
  en: {
    types: {
      technical: 'Technical',
      behavioral: 'Behavioural',
      hr: 'HR screening',
      mixed: 'Mixed',
    },
    statuses: {
      ready: 'Not started',
      in_progress: 'In progress',
      paused: 'Paused',
      ended: 'Ended',
      failed: 'Failed',
    },
    difficulties: { easy: 'Easy', medium: 'Medium', hard: 'Hard' },
    execution: { local: 'On this computer', cloud: 'ChatGPT plan' },
  },
  it: {
    types: {
      technical: 'Tecnico',
      behavioral: 'Comportamentale',
      hr: 'Conoscitivo (HR)',
      mixed: 'Misto',
    },
    statuses: {
      ready: 'Non iniziato',
      in_progress: 'In corso',
      paused: 'In pausa',
      ended: 'Concluso',
      failed: 'Non riuscito',
    },
    difficulties: { easy: 'Facile', medium: 'Media', hard: 'Difficile' },
    execution: { local: 'Su questo computer', cloud: 'Piano ChatGPT' },
  },
})

type Labels = (typeof interviewLabels)['en']

/** The label of a known key, or the key itself for values added later. */
export function labelOf(
  labels: Labels,
  group: 'types' | 'statuses' | 'difficulties' | 'execution',
  key: string,
): string {
  const table = labels[group] as Readonly<Record<string, string>>
  return table[key] ?? key
}

export const isInterviewType = (value: string | null): value is InterviewType =>
  INTERVIEW_TYPES.some((type) => type === value)
