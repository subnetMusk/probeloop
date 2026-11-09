import { describe, expect, it } from 'vitest'

import { pageOf } from './pagination'

describe('pageOf', () => {
  const items = Array.from({ length: 11 }, (_, i) => i)

  it('cuts a list into pages', () => {
    expect(pageOf(items, 0, 5)).toEqual({ items: [0, 1, 2, 3, 4], page: 0, pages: 3, total: 11 })
    expect(pageOf(items, 2, 5).items).toEqual([10])
  })

  it('keeps the page within range', () => {
    expect(pageOf(items, 9, 5).page).toBe(2)
    expect(pageOf(items, -1, 5).page).toBe(0)
    expect(pageOf([], 3, 5)).toEqual({ items: [], page: 0, pages: 1, total: 0 })
  })
})
