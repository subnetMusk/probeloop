import { describe, expect, it } from 'vitest'

import { clock } from './format'

describe('clock', () => {
  it('formats minutes and seconds', () => {
    expect(clock(0)).toBe('0:00')
    expect(clock(65.9)).toBe('1:05')
    expect(clock(600)).toBe('10:00')
    expect(clock(-3)).toBe('0:00')
  })
})
