import type { Step } from '@/entities/preparation'

/** The address of a preparation step. */
export const stepPath = (step: Step) => `/new-interview/${step}` as const
