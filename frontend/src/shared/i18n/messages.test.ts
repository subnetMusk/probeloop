import { describe, expect, it } from 'vitest'

import { PROBLEMS_IT, localizeProblem } from '@/shared/api/problem-messages'
import { defineMessages, getMessages, messageKeys, plural } from './messages'

const sample = defineMessages({
  en: {
    title: 'Report',
    answers: (count: number) => `${String(count)} answers`,
    section: { summary: 'Summary' },
  },
  it: {
    title: 'Report',
    answers: (count: number) => `${String(count)} risposte`,
    section: { summary: 'Sintesi' },
  },
})

describe('typed messages', () => {
  it('returns the messages of a language, with typed parameters', () => {
    expect(getMessages(sample, 'it').answers(3)).toBe('3 risposte')
    expect(getMessages(sample, 'en').section.summary).toBe('Summary')
  })

  it('has the same keys in both languages', () => {
    expect(messageKeys(sample.it)).toEqual(messageKeys(sample.en))
  })

  it('rejects a dictionary with a missing translation at compile time', () => {
    defineMessages({
      en: { title: 'Report', subtitle: 'Version' },
      // @ts-expect-error -- `subtitle` is missing in Italian.
      it: { title: 'Report' },
    })
  })

  it('chooses plural forms by language', () => {
    const forms = { one: 'risposta', other: 'risposte' }
    expect(plural(1, 'it', forms)).toBe('risposta')
    expect(plural(0, 'it', forms)).toBe('risposte')
    expect(plural(2, 'en', { one: 'answer', other: 'answers' })).toBe('answers')
  })
})

describe('backend problem messages', () => {
  it('translates known details and keeps unknown ones', () => {
    expect(localizeProblem('interview not found', 'it')).toBe('Colloquio non trovato')
    expect(localizeProblem('interview not found', 'en')).toBe('interview not found')
    expect(localizeProblem('a message with a 42 inside', 'it')).toBe('a message with a 42 inside')
  })

  it('has an Italian text for every listed message', () => {
    for (const [english, italian] of Object.entries(PROBLEMS_IT)) {
      expect(italian.trim(), english).not.toBe('')
    }
  })
})
