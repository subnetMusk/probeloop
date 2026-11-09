import { describe, expect, it } from 'vitest'

import { clock, minutes, relativeDay, score, shortDate } from './format'

describe('clock', () => {
  it('formats minutes and seconds', () => {
    expect(clock(0)).toBe('0:00')
    expect(clock(65.9)).toBe('1:05')
    expect(clock(600)).toBe('10:00')
    expect(clock(-3)).toBe('0:00')
  })
})

describe('compact formats', () => {
  it('rounds durations to minutes', () => {
    expect(minutes(42)).toBe('42 s')
    expect(minutes(580.4)).toBe('10 min')
    expect(minutes(3900)).toBe('1 h 5 min')
    expect(minutes(7200)).toBe('2 h')
  })

  it('names recent days and dates older ones', () => {
    const now = new Date(2026, 10, 8, 18, 0).getTime() / 1000
    const at = (day: number) => new Date(2026, 10, day, 9, 30).getTime() / 1000
    expect(relativeDay(at(8), 'en', now)).toBe('today')
    expect(relativeDay(at(7), 'it', now)).toBe('ieri')
    expect(relativeDay(at(5), 'en', now)).toBe('3 days ago')
    expect(relativeDay(at(1), 'en', now)).toBe(shortDate(at(1), 'en'))
  })

  it('writes scores with one decimal in the interface language', () => {
    expect(score(4.11, 'en')).toBe('4.1')
    expect(score(4.6, 'it')).toBe('4,6')
  })
})
