import { describe, expect, it } from 'vitest'

import type { ProgressGroup } from '@/shared/api'
import { trendLines, typesWithScores } from './series'

type Point = ProgressGroup['points'][number]

function point(id: string, at: number, overall: number | null, type: string | null): Point {
  return {
    report_id: id,
    subject_id: `s-${id}`,
    session_id: type ? `s-${id}` : null,
    created_at: at,
    version: 1,
    overall,
    values: {},
    evidence_counts: {},
    interview_type: type,
    profile_id: null,
    role: null,
    rubric_id: 'r',
    rubric_hash: 'h',
    model_ref: 'model',
    prompt_ref: 'p',
    language: 'it',
  }
}

function group(id: string, scorer: string, kind: string, points: Point[]): ProgressGroup {
  return {
    id,
    scorer_key: scorer,
    kind,
    rubric_id: 'r',
    rubric_hash: 'h',
    model_ref: `model-${scorer}`,
    language: 'it',
    criteria: {},
    points,
  }
}

describe('trend lines', () => {
  const groups = [
    // Two comparison groups with the same scorer: different criteria, one line.
    group('g1', 'A', 'interview', [point('t1', 1, 3.5, 'technical'), point('h1', 2, 4, 'hr')]),
    group('g2', 'A', 'interview', [point('t2', 3, 4.1, 'technical')]),
    // Another evaluator: a new run on the same line.
    group('g3', 'B', 'interview', [point('t3', 5, 4.4, 'technical'), point('x', 6, null, 'hr')]),
    group('g4', 'A', 'cv', [point('c1', 4, 3.7, null)]),
  ]

  it('joins points scored the same way and breaks where the evaluator changes', () => {
    const lines = trendLines(groups, 'interview')
    expect(lines.map((l) => l.key)).toEqual(['technical', 'hr'])
    const technical = lines[0]?.segments.map((run) => run.map((p) => p.reportId))
    expect(technical).toEqual([['t1', 't2'], ['t3']])
    expect(lines[1]?.segments).toHaveLength(1)
  })

  it('filters by interview type and leaves out reports without a score', () => {
    const hr = trendLines(groups, 'interview', 'hr')
    expect(hr.map((l) => l.segments.flat().map((p) => p.reportId))).toEqual([['h1']])
    expect(typesWithScores(groups)).toEqual(['technical', 'hr'])
  })

  it('keeps CV checks on their own line', () => {
    const cv = trendLines(groups, 'cv')
    expect(cv).toEqual([{ key: 'cv', segments: [[expect.objectContaining({ reportId: 'c1' })]] }])
  })
})
