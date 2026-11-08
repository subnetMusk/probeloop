import { describe, expect, it } from 'vitest'

import type { DocumentView, FactView, PreparationView } from '@/shared/api'
import { summarise } from './summary'

function fact(id: string, patch: Partial<FactView> = {}): FactView {
  return {
    id,
    subject: 'candidate',
    kind: 'skill',
    statement: id,
    text: id,
    origin: 'declared',
    document_id: 'cv',
    quote: id,
    review: 'pending',
    corrected: null,
    ...patch,
  }
}

function document(id: string, warnings: string[] = []): DocumentView {
  return {
    id,
    kind: 'cv',
    title: id,
    origin: 'typed',
    media_type: 'text/plain',
    filename: null,
    created_at: 0,
    has_original: false,
    chars: 10,
    warnings,
    preview: '',
  }
}

function preparation(facts: FactView[], patch: Partial<PreparationView> = {}): PreparationView {
  return {
    id: 'p',
    status: 'review',
    language: 'it',
    job_mode: 'offer',
    documents: [document('cv'), document('offer')],
    facts,
    matches: [],
    area: null,
    vocabulary: [],
    error: null,
    snapshot_id: null,
    created_at: 0,
    profile_id: null,
    execution_profile: 'local',
    analysis: null,
    ...patch,
  }
}

describe('fact review summary', () => {
  it('opens inferred facts and facts from documents with warnings', () => {
    const facts = [
      fact('declared'),
      fact('inferred', { origin: 'inferred', quote: null }),
      fact('checked', { origin: 'inferred', review: 'confirmed' }),
      fact('hidden', { document_id: 'offer' }),
    ]
    const summary = summarise(
      preparation(facts, { documents: [document('cv'), document('offer', ['hidden text'])] }),
    )
    expect(summary.doubtful.map((f) => f.id)).toEqual(['inferred', 'checked', 'hidden'])
    expect(summary.open).toBe(2)
    expect(summary.counts).toEqual({ declared: 2, confirmed: 1, excluded: 0, total: 4 })
  })

  it('lists requirements that are not shown first, without excluded evidence', () => {
    const facts = [
      fact('python'),
      fact('kafka-claim', { review: 'excluded' }),
      fact('r-python', { subject: 'job', kind: 'requirement' }),
      fact('r-kafka', { subject: 'job', kind: 'nice_to_have' }),
      fact('r-dropped', { subject: 'job', kind: 'requirement', review: 'excluded' }),
    ]
    const matches = [
      { requirement_id: 'r-python', status: 'met', fact_ids: ['python'], rationale: 'ok' },
      { requirement_id: 'r-kafka', status: 'partial', fact_ids: ['kafka-claim'], rationale: '' },
      { requirement_id: 'r-dropped', status: 'met', fact_ids: [], rationale: '' },
    ]
    const summary = summarise(preparation(facts, { matches }))
    expect(summary.requirements.map((r) => [r.id, r.kind, r.status, r.supporting])).toEqual([
      ['r-kafka', 'nice_to_have', 'partial', []],
      ['r-python', 'requirement', 'met', ['python']],
    ])
  })
})
