import { describe, expect, it } from 'vitest'

import type { ProgressGroup } from '@/shared/api'
import { trendLines, typesWithScores } from './series'

type Point = ProgressGroup['points'][number]

const BACKEND = { profession: 'Software', target_role: 'Backend developer', seniority: 'mid' }

function point(
  id: string,
  at: number,
  overall: number | null,
  type: string | null,
  patch: Partial<Point> = {},
): Point {
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
    profile_id: 'pr1',
    role: BACKEND,
    rubric_id: 'hr.v2+technical.v3',
    rubric_hash: 'h1',
    model_ref: 'model-a',
    prompt_ref: 'p1',
    language: 'it',
    ...patch,
  }
}

function group(id: string, kind: string, points: Point[]): ProgressGroup {
  return {
    id,
    scorer_key: id,
    kind,
    rubric_id: 'r',
    rubric_hash: 'h',
    model_ref: 'model',
    language: 'it',
    criteria: {},
    points,
  }
}

const ids = (segments: { reportId: string }[][]) =>
  segments.map((run) => run.map((p) => p.reportId))

describe('trend lines', () => {
  it('follows one profile across changes of evaluator, marking them', () => {
    const groups = [
      group('g1', 'interview', [point('a', 1, 60, 'technical')]),
      group('g2', 'interview', [
        point('b', 2, 65, 'hr', { model_ref: 'model-b', rubric_id: 'hr.v2', rubric_hash: 'h2' }),
      ]),
      group('g3', 'interview', [
        point('c', 3, 70, 'technical', {
          language: 'en',
          role: { ...BACKEND, seniority: 'Senior' },
        }),
      ]),
    ]
    const [line, ...others] = trendLines(groups, 'interview')
    expect(others).toEqual([])
    expect(line?.key).toBe('profile:pr1')
    expect(ids(line?.segments ?? [])).toEqual([['a', 'b', 'c']])
    expect(line?.segments.flat().map((p) => p.changes)).toEqual([
      [],
      ['model'],
      ['model', 'language', 'role'],
    ])
  })

  it('breaks a line only where a rubric version changes', () => {
    const groups = [
      group('g1', 'interview', [
        point('a', 1, 60, 'technical'),
        point('b', 2, 62, 'technical', { rubric_id: 'technical.v4+hr.v2', rubric_hash: 'h3' }),
        point('c', 3, 64, 'technical', { rubric_id: 'technical.v4+hr.v2', rubric_hash: 'h4' }),
        point('d', 4, 66, 'behavioral', { rubric_id: 'behavioral.v2', rubric_hash: 'h5' }),
      ]),
    ]
    const [line] = trendLines(groups, 'interview')
    // A new version breaks; the same reference with other content breaks too.
    expect(ids(line?.segments ?? [])).toEqual([['a'], ['b'], ['c', 'd']])
  })

  it('gives each profile its own line, and reports without one a line per role', () => {
    const groups = [
      group('g1', 'interview', [
        point('a', 1, 60, 'technical'),
        point('b', 2, 61, 'technical', { profile_id: 'pr2' }),
        point('c', 3, 62, 'hr', { profile_id: null, role: { ...BACKEND, seniority: ' MID ' } }),
        point('d', 4, 63, 'hr', { profile_id: null, role: null }),
        point('x', 5, null, 'hr'),
      ]),
      group('g2', 'cv', [point('cv', 6, 70, null, { rubric_id: 'cv.v1' })]),
    ]
    const lines = trendLines(groups, 'interview')
    expect(lines.map((l) => l.key)).toEqual([
      'none',
      'role:software / backend developer / mid',
      'profile:pr2',
      'profile:pr1',
    ])
    expect(trendLines(groups, 'interview', 'hr').map((l) => l.key)).toEqual([
      'none',
      'role:software / backend developer / mid',
    ])
    expect(trendLines(groups, 'cv').map((l) => ids(l.segments))).toEqual([[['cv']]])
    expect(typesWithScores(groups)).toEqual(['technical', 'hr'])
  })
})
