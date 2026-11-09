import { describe, expect, it } from 'vitest'

import type { ReportData, SessionView } from '@/shared/api'
import { bandOf, firstReason, median, toCvReportView, toInterviewReportView } from './report-view'

const quote = (text: string, turn: number | null) => ({
  source_id: turn === null ? 'doc' : `turn-${String(turn)}`,
  quote: text,
  turn_seq: turn,
})

function report(patch: Partial<ReportData> = {}): ReportData {
  return {
    id: 'r1',
    kind: 'interview',
    subject_id: 's1',
    session_id: 's1',
    snapshot_id: null,
    version: 2,
    created_at: 100,
    language: 'it',
    rubric_id: 'interview.v1',
    rubric_hash: 'a'.repeat(64),
    model_ref: 'chatgpt:gpt-6.1-terra',
    prompt_ref: 'judge_unit@v3',
    input_fingerprint: 'b'.repeat(64),
    overall: 3.9,
    assessed: 4,
    criteria: 5,
    dropped: 1,
    duration_s: 120,
    disclaimer: 'Valutazione formativa.',
    units: [
      { id: 'u0', topic_id: 't1', kind: 'technical', question_seqs: [0, 2], answer_seqs: [1, 3] },
      { id: 'u4', topic_id: 't9', kind: 'logistics', question_seqs: [4], answer_seqs: [5] },
    ],
    unit_scores: [
      {
        criterion_id: 'technical.accuracy',
        label: 'Correttezza',
        value: 4,
        reason: 'Spiega bene il partizionamento.\nPartizionamento corretto.',
        evidence: [quote('partizioni per cliente', 3)],
        unstable: false,
        unit_id: 'u0',
      },
    ],
    scores: [
      {
        criterion_id: 'technical.accuracy',
        label: 'Correttezza',
        value: 4,
        reason: '1/1',
        evidence: [quote('partizioni per cliente', 3)],
        unstable: false,
        unit_id: null,
      },
    ],
    observations: [
      {
        kind: 'summary',
        text: 'Buona base tecnica.',
        evidence: [],
        replacement: null,
        unit_id: null,
      },
      {
        kind: 'technical_error',
        text: 'Kafka non garantisce l’ordine tra partizioni.',
        evidence: [quote('ordine globale', 1)],
        replacement: 'L’ordine è garantito solo dentro una partizione.',
        unit_id: 'u0',
      },
      {
        kind: 'strength',
        text: 'Esempi concreti.',
        evidence: [],
        replacement: null,
        unit_id: 'u0',
      },
      {
        kind: 'question',
        text: 'Come gestiresti i retry?',
        evidence: [],
        replacement: null,
        unit_id: null,
      },
    ],
    checks: [
      { id: 'topic:t1', status: 'covered', detail: 'Kafka', evidence: [] },
      {
        id: 'requirement:f1',
        status: 'discussed_model',
        detail: 'Kafka',
        evidence: [quote('Kafka', 1)],
      },
      { id: 'document_requirement:f1', status: 'partial', detail: 'Kafka', evidence: [] },
      { id: 'document_requirement:f2', status: 'met', detail: 'Python', evidence: [] },
    ],
    delivery: [
      { id: 'answer_duration', value: 30, unit: 's', detail: '', turn_seq: 1 },
      { id: 'speaking_rate', value: 120, unit: 'words/min', detail: '', turn_seq: 1 },
      { id: 'fillers', value: 2, unit: 'count', detail: '', turn_seq: 1 },
      { id: 'answer_latency', value: 1.5, unit: 's', detail: '', turn_seq: 1 },
      { id: 'answer_duration', value: 30, unit: 's', detail: '', turn_seq: 3 },
      { id: 'speaking_rate', value: 140, unit: 'words/min', detail: '', turn_seq: 3 },
      { id: 'fillers', value: 1, unit: 'count', detail: '', turn_seq: 3 },
      { id: 'answer_latency', value: null, unit: 's', detail: '', turn_seq: 3 },
      { id: 'candidate_talk_share', value: 62.5, unit: '%', detail: '', turn_seq: null },
    ],
    revisions: [
      { seq: 1, revision: 1 },
      { seq: 3, revision: 2 },
    ],
    ...patch,
  }
}

function turn(seq: number, speaker: string, text: string, revisions: string[] = [text]) {
  return {
    seq,
    speaker,
    text,
    elapsed_s: seq * 10,
    audio: speaker === 'candidate' ? `/audio/${String(seq)}.wav` : null,
    action: null,
    status: null,
    topic_id: 't1',
    words: [],
    revisions: revisions.map((t, i) => ({
      number: i + 1,
      text: t,
      source: i === 0 ? 'stt' : 'user_edit',
      engine_ref: null,
      created_at: 0,
    })),
  }
}

const session = {
  id: 's1',
  topics: [{ id: 't1', title: 'Kafka in produzione' }],
  turns: [
    turn(0, 'interviewer', 'Come usi Kafka?'),
    turn(1, 'candidate', 'Con un ordine globale.'),
    turn(2, 'interviewer', 'E le partizioni?'),
    turn(3, 'candidate', 'Ultima versione.', [
      'Prima versione.',
      'Partizioni per cliente.',
      'Ultima versione.',
    ]),
    turn(4, 'interviewer', 'Domande?'),
    turn(5, 'candidate', 'Nessuna.'),
  ],
} as unknown as SessionView

describe('interview report view', () => {
  const view = toInterviewReportView(report(), session)

  it('leads with the score, its band and the summary', () => {
    expect([view.overall, view.band]).toEqual([3.9, 'developing'])
    expect(view.summary?.text).toBe('Buona base tecnica.')
  })

  it('lists each note once, with its question block and numbered answers', () => {
    expect(view.improvements.map((n) => [n.kind, n.unit, n.replacement])).toEqual([
      ['technical_error', 1, 'L’ordine è garantito solo dentro una partizione.'],
    ])
    expect(view.improvements[0]?.quotes).toEqual([
      { text: 'ordine globale', answer: 1, turnSeq: 1 },
    ])
    expect(view.strengths.map((n) => n.text)).toEqual(['Esempi concreti.'])
    expect(view.practice.map((n) => n.text)).toEqual(['Come gestiresti i retry?'])
  })

  it('shows each block with its questions, the assessed answers and one reason per score', () => {
    const [first, closing] = view.units
    expect(first?.topic).toBe('Kafka in produzione')
    expect(first?.questions.map((q) => q.text)).toEqual(['Come usi Kafka?', 'E le partizioni?'])
    // The report judged revision 2 of the second answer, not the later edit.
    expect(first?.answers.map((a) => [a.number, a.text])).toEqual([
      [1, 'Con un ordine globale.'],
      [2, 'Partizioni per cliente.'],
    ])
    expect(first?.scores[0]?.reason).toBe('Spiega bene il partizionamento.')
    expect(closing?.scored).toBe(false)
  })

  it('puts the interview and the documents side by side for each requirement', () => {
    expect(view.requirements).toEqual([
      expect.objectContaining({ id: 'f1', interview: 'discussed', documents: 'partial' }),
      expect.objectContaining({ id: 'f2', interview: null, documents: 'met' }),
    ])
    expect(view.topics).toEqual([{ title: 'Kafka', coverage: 'covered' }])
  })

  it('summarises delivery with medians and rates', () => {
    expect(view.delivery).toMatchObject({
      medianRate: 130,
      medianLatency: 1.5,
      fillersPerMinute: 3,
      talkShare: 62.5,
      budgetShare: null,
    })
    expect(view.delivery?.perAnswer.map((a) => a.answer)).toEqual([1, 2])
  })

  it('keeps technical details short', () => {
    expect(view.about).toMatchObject({
      rubricHash: 'aaaaaaaa',
      fingerprint: 'bbbbbbbb',
      dropped: 1,
    })
    expect(view.about.editedAnswers).toBe(1)
  })

  it('numbers answers from the report when the interview is gone', () => {
    const alone = toInterviewReportView(report())
    expect(alone.units[0]?.answers.map((a) => [a.number, a.text])).toEqual([
      [1, ''],
      [2, ''],
    ])
  })
})

describe('CV report view', () => {
  it('orders the checks from what to review to what cannot be assessed', () => {
    const view = toCvReportView(
      report({
        kind: 'cv',
        session_id: null,
        checks: [
          { id: 'text', status: 'pass', detail: 'Caratteri: 900', evidence: [] },
          { id: 'visual_layout', status: 'not_assessable', detail: 'Layout', evidence: [] },
          { id: 'contact', status: 'review', detail: 'Email assente', evidence: [] },
          {
            id: 'quantification',
            status: 'info',
            detail: 'Misure: 2',
            evidence: [quote('40%', null)],
          },
        ],
        observations: [
          {
            kind: 'rewrite',
            text: 'Più concreto.',
            evidence: [],
            replacement: 'Ho ridotto…',
            unit_id: null,
          },
          {
            kind: 'improvement',
            text: 'Aggiungi risultati.',
            evidence: [],
            replacement: null,
            unit_id: null,
          },
        ],
      }),
    )
    expect(view.checks.map((c) => c.status)).toEqual(['review', 'info', 'pass', 'not_assessable'])
    expect(view.checks[1]?.quotes).toEqual([{ text: '40%', answer: null, turnSeq: null }])
    expect(view.rewrites.map((n) => n.replacement)).toEqual(['Ho ridotto…'])
    expect(view.improvements.map((n) => n.text)).toEqual(['Aggiungi risultati.'])
  })
})

describe('helpers', () => {
  it('bands, reasons and medians', () => {
    expect([bandOf(4), bandOf(2.5), bandOf(2.4), bandOf(null)]).toEqual([
      'solid',
      'developing',
      'needs_work',
      null,
    ])
    expect(firstReason('\nPrimo.\nSecondo.')).toBe('Primo.')
    expect([median([]), median([3, 1, 2]), median([1, 2, 3, 4])]).toEqual([null, 2, 2.5])
  })
})
