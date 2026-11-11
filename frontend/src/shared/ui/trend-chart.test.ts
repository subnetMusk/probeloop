import { describe, expect, it } from 'vitest'

import { monotonePath } from './trend-chart'

/** The y of every point and control point in a path of M, L and C commands. */
function ys(path: string): number[] {
  return [...path.matchAll(/-?\d+(?:\.\d+)?,(-?\d+(?:\.\d+)?)/g)].map((match) => Number(match[1]))
}

describe('monotone path', () => {
  it('joins one or two points with straight lines', () => {
    expect(monotonePath([[0, 5]])).toBe('M0,5')
    expect(
      monotonePath([
        [0, 5],
        [10, 15],
      ]),
    ).toBe('M0,5L10,15')
  })

  it('never goes beyond the values it joins', () => {
    const points = [
      [0, 80],
      [10, 40],
      [20, 40],
      [30, 90],
      [40, 85],
    ] as const
    const path = monotonePath(points)
    expect(path.startsWith('M0,80C')).toBe(true)
    expect(Math.min(...ys(path))).toBeGreaterThanOrEqual(40)
    expect(Math.max(...ys(path))).toBeLessThanOrEqual(90)
  })

  it('keeps a flat stretch flat', () => {
    const path = monotonePath([
      [0, 10],
      [10, 50],
      [20, 50],
      [30, 70],
    ])
    // The segment between the two equal values has both control points at 50.
    const segment = path.split('C')[2] ?? ''
    expect(ys(segment)).toEqual([50, 50, 50])
  })
})
