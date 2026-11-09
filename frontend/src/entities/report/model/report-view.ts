import type { ReportData, SessionView } from '@/shared/api'

/**
 * View models of the reports (ADR 0014): pure functions from the stored report, and the
 * interview when there is one, to what the pages show, in reading order. Raw identifiers (unit
 * and check ids, turn numbers) never reach the page: answers are numbered as the candidate gave
 * them, and only the first reason of each judge is kept.
 */

export type Band = 'solid' | 'developing' | 'needs_work'
export const INTERVIEW_SECTIONS = [
  'overview',
  'improvements',
  'strengths',
  'questions',
  'requirements',
  'delivery',
  'practice',
  'technical',
] as const
export const CV_SECTIONS = [
  'overview',
  'criteria',
  'requirements',
  'checks',
  'improvements',
  'strengths',
  'rewrites',
  'practice',
  'original',
  'technical',
] as const

/** The same thresholds as the exports: 4 and above is solid, below 2.5 needs work. */
export function bandOf(value: number | null): Band | null {
  if (value === null) return null
  if (value >= 4) return 'solid'
  if (value >= 2.5) return 'developing'
  return 'needs_work'
}

export interface QuoteView {
  text: string
  /** The answer the quote comes from, numbered from 1; null for documents. */
  answer: number | null
  turnSeq: number | null
}

export interface NoteView {
  kind: string
  text: string
  /** A better wording, or the correct statement of a technical error. */
  replacement: string | null
  quotes: QuoteView[]
  /** The question-and-answer block the note is about, numbered from 1. */
  unit: number | null
}

export interface CriterionView {
  id: string
  label: string
  value: number | null
  band: Band | null
  reason: string
  unstable: boolean
  quotes: QuoteView[]
}

export interface AnswerView {
  seq: number
  number: number
  text: string
  audio: string | null
}

export interface UnitView {
  id: string
  number: number
  kind: string
  /** Logistics and questions of an unclear kind are kept but not scored. */
  scored: boolean
  topic: string | null
  questions: { seq: number; text: string }[]
  answers: AnswerView[]
  scores: CriterionView[]
}

export interface RequirementCoverage {
  id: string
  text: string
  /** Whether the interview touched it, as the model reads the answers. */
  interview: 'discussed' | 'not_shown' | null
  /** How the documents cover it, from the approved context. */
  documents: 'met' | 'partial' | 'not_shown' | null
  quotes: QuoteView[]
}

export interface AnswerDelivery {
  seq: number
  answer: number
  duration: number | null
  rate: number | null
  fillers: number | null
  pauses: number | null
  latency: number | null
}

export interface DeliverySummary {
  medianRate: number | null
  medianLatency: number | null
  fillersPerMinute: number | null
  longPauses: number | null
  talkShare: number | null
  budgetShare: number | null
  perAnswer: AnswerDelivery[]
}

export interface AboutView {
  version: number
  createdAt: number
  durationS: number
  model: string
  prompt: string
  rubric: string
  rubricHash: string
  fingerprint: string
  dropped: number
  disclaimer: string
  editedAnswers: number
}

export interface InterviewReportView {
  sections: readonly string[]
  overall: number | null
  band: Band | null
  assessed: number
  criteriaCount: number
  summary: NoteView | null
  /**
   * Priorities first, as the summary chose them; technical errors carry their correction. Notes
   * appear once, here or under strengths and practice, with the block they refer to.
   */
  improvements: NoteView[]
  strengths: NoteView[]
  practice: NoteView[]
  criteria: CriterionView[]
  units: UnitView[]
  requirements: RequirementCoverage[]
  topics: { title: string; coverage: string }[]
  delivery: DeliverySummary | null
  about: AboutView
}

export interface CvCheckView {
  id: string
  status: 'review' | 'info' | 'pass' | 'not_assessable'
  detail: string
  quotes: QuoteView[]
}

export interface CvReportView {
  sections: readonly string[]
  overall: number | null
  band: Band | null
  assessed: number
  criteriaCount: number
  summary: NoteView | null
  criteria: CriterionView[]
  improvements: NoteView[]
  strengths: NoteView[]
  rewrites: NoteView[]
  practice: NoteView[]
  /** Deterministic checks: what to review first, then information, then what passed. */
  checks: CvCheckView[]
  about: AboutView
}

const IMPROVEMENT_KINDS = new Set(['improvement', 'technical_error', 'rewrite'])

/** The first judge's reason: paired judgements join two reasons with a line break. */
export function firstReason(reason: string): string {
  return (
    reason
      .split('\n')
      .find((line) => line.trim() !== '')
      ?.trim() ?? ''
  )
}

export function median(values: readonly number[]): number | null {
  if (values.length === 0) return null
  const sorted = [...values].sort((a, b) => a - b)
  const middle = Math.floor(sorted.length / 2)
  const value =
    sorted.length % 2 ? sorted[middle] : ((sorted[middle - 1] ?? 0) + (sorted[middle] ?? 0)) / 2
  return value ?? null
}

/** Answer numbers by turn: the order in which the candidate answered. */
function answerNumbers(report: ReportData, session: SessionView | undefined): Map<number, number> {
  const seqs = session
    ? session.turns.filter((t) => t.speaker === 'candidate').map((t) => t.seq)
    : report.units.flatMap((u) => u.answer_seqs)
  return new Map([...new Set(seqs)].sort((a, b) => a - b).map((seq, i) => [seq, i + 1]))
}

function about(report: ReportData): AboutView {
  return {
    version: report.version,
    createdAt: report.created_at,
    durationS: report.duration_s,
    model: report.model_ref,
    prompt: report.prompt_ref,
    rubric: report.rubric_id,
    rubricHash: report.rubric_hash.slice(0, 8),
    fingerprint: report.input_fingerprint.slice(0, 8),
    dropped: report.dropped,
    disclaimer: report.disclaimer,
    editedAnswers: report.revisions.filter((r) => r.revision > 1).length,
  }
}

type Evidence = ReportData['scores'][number]['evidence']

function quotesOf(evidence: Evidence, answers: Map<number, number>): QuoteView[] {
  return evidence.map((e) => ({
    text: e.quote,
    turnSeq: e.turn_seq ?? null,
    answer:
      e.turn_seq === null || e.turn_seq === undefined ? null : (answers.get(e.turn_seq) ?? null),
  }))
}

function criterion(
  score: ReportData['scores'][number],
  answers: Map<number, number>,
): CriterionView {
  return {
    id: score.criterion_id,
    label: score.label,
    value: score.value ?? null,
    band: bandOf(score.value ?? null),
    reason: firstReason(score.reason),
    unstable: score.unstable,
    quotes: quotesOf(score.evidence, answers),
  }
}

function notesOf(
  report: ReportData,
  answers: Map<number, number>,
  units: Map<string, number>,
): NoteView[] {
  return report.observations.map((o) => ({
    kind: o.kind,
    text: o.text,
    replacement: o.replacement ?? null,
    quotes: quotesOf(o.evidence, answers),
    unit: o.unit_id ? (units.get(o.unit_id) ?? null) : null,
  }))
}

/** Aggregates of the delivery measures: medians and rates rather than one number per answer. */
export function deliveryOf(
  report: ReportData,
  answers: Map<number, number>,
): DeliverySummary | null {
  if (report.delivery.length === 0) return null
  const byTurn = new Map<number, Record<string, number | null>>()
  const global: Record<string, number | null> = {}
  for (const metric of report.delivery) {
    const value = metric.value ?? null
    if (metric.turn_seq === null) global[metric.id] = value
    else byTurn.set(metric.turn_seq, { ...byTurn.get(metric.turn_seq), [metric.id]: value })
  }
  const perAnswer: AnswerDelivery[] = [...byTurn.entries()]
    .sort(([a], [b]) => a - b)
    .map(([seq, m]) => ({
      seq,
      answer: answers.get(seq) ?? 0,
      duration: m.answer_duration ?? null,
      rate: m.speaking_rate ?? null,
      fillers: m.fillers ?? null,
      pauses: m.long_pauses ?? null,
      latency: m.answer_latency ?? null,
    }))
  const known = (pick: (a: AnswerDelivery) => number | null) =>
    perAnswer.map(pick).filter((v): v is number => v !== null)
  const seconds = known((a) => a.duration).reduce((sum, v) => sum + v, 0)
  const fillers = known((a) => a.fillers)
  const pauses = known((a) => a.pauses)
  return {
    medianRate: median(known((a) => a.rate)),
    medianLatency: median(known((a) => a.latency)),
    fillersPerMinute:
      seconds > 0 && fillers.length
        ? Math.round((fillers.reduce((s, v) => s + v, 0) / (seconds / 60)) * 10) / 10
        : null,
    longPauses: pauses.length ? pauses.reduce((s, v) => s + v, 0) : null,
    talkShare: global.candidate_talk_share ?? null,
    budgetShare: global.answer_budget_share ?? null,
    perAnswer,
  }
}

/** Requirements of the position: what the interview touched, next to what the documents show. */
function requirementsOf(report: ReportData, answers: Map<number, number>): RequirementCoverage[] {
  const rows = new Map<string, RequirementCoverage>()
  const row = (id: string, text: string) => {
    const existing = rows.get(id)
    if (existing) return existing
    const created: RequirementCoverage = { id, text, interview: null, documents: null, quotes: [] }
    rows.set(id, created)
    return created
  }
  for (const check of report.checks) {
    const [prefix, id] = check.id.split(/:(.*)/s)
    if (!id) continue
    if (prefix === 'requirement') {
      const target = row(id, check.detail)
      target.interview = check.status === 'not_shown' ? 'not_shown' : 'discussed'
      target.quotes = quotesOf(check.evidence, answers)
    } else if (prefix === 'document_requirement') {
      const status = check.status
      row(id, check.detail).documents =
        status === 'met' || status === 'partial' ? status : 'not_shown'
    }
  }
  return [...rows.values()]
}

export function toInterviewReportView(
  report: ReportData,
  session?: SessionView,
): InterviewReportView {
  const answers = answerNumbers(report, session)
  const turns = new Map(session?.turns.map((t) => [t.seq, t]))
  const assessedRevision = new Map(report.revisions.map((r) => [r.seq, r.revision]))
  const topics = new Map(session?.topics.map((t) => [t.id ?? '', t.title ?? '']))
  const unitNumbers = new Map(report.units.map((u, i) => [u.id, i + 1]))
  const notes = notesOf(report, answers, unitNumbers)
  const units: UnitView[] = report.units.map((unit, index) => ({
    id: unit.id,
    number: index + 1,
    kind: unit.kind,
    scored: unit.kind !== 'logistics' && unit.kind !== 'unclassified',
    topic: topics.get(unit.topic_id) ?? null,
    questions: unit.question_seqs.map((seq) => ({ seq, text: turns.get(seq)?.text ?? '' })),
    answers: unit.answer_seqs.map((seq) => {
      const turn = turns.get(seq)
      // The report judged the revision that was current when it was generated.
      const revision = turn?.revisions.find((r) => r.number === assessedRevision.get(seq))
      return {
        seq,
        number: answers.get(seq) ?? 0,
        text: revision?.text ?? turn?.text ?? '',
        audio: turn?.audio ?? null,
      }
    }),
    scores: report.unit_scores
      .filter((s) => s.unit_id === unit.id)
      .map((s) => criterion(s, answers)),
  }))
  const topicChecks = report.checks.filter((c) => c.id.startsWith('topic:'))
  return {
    sections: INTERVIEW_SECTIONS,
    overall: report.overall ?? null,
    band: bandOf(report.overall ?? null),
    assessed: report.assessed,
    criteriaCount: report.criteria,
    summary: notes.find((n) => n.kind === 'summary') ?? null,
    improvements: notes.filter((n) => IMPROVEMENT_KINDS.has(n.kind)),
    strengths: notes.filter((n) => n.kind === 'strength'),
    practice: notes.filter((n) => n.kind === 'question'),
    criteria: report.scores.map((s) => criterion(s, answers)),
    units,
    requirements: requirementsOf(report, answers),
    topics: topicChecks.map((c) => ({ title: c.detail, coverage: c.status })),
    delivery: deliveryOf(report, answers),
    about: about(report),
  }
}

const CHECK_ORDER = { review: 0, info: 1, pass: 2, not_assessable: 3 } as const

function checkStatus(status: string): CvCheckView['status'] {
  return status === 'review' || status === 'info' || status === 'pass' ? status : 'not_assessable'
}

export function toCvReportView(report: ReportData): CvReportView {
  const none = new Map<number, number>()
  const notes = notesOf(report, none, new Map())
  const checks: CvCheckView[] = report.checks
    .map((c) => ({
      id: c.id,
      status: checkStatus(c.status),
      detail: c.detail,
      quotes: quotesOf(c.evidence, none),
    }))
    .sort((a, b) => CHECK_ORDER[a.status] - CHECK_ORDER[b.status])
  return {
    sections: CV_SECTIONS,
    overall: report.overall ?? null,
    band: bandOf(report.overall ?? null),
    assessed: report.assessed,
    criteriaCount: report.criteria,
    summary: notes.find((n) => n.kind === 'summary') ?? null,
    criteria: report.scores.map((s) => criterion(s, none)),
    improvements: notes.filter((n) => n.kind === 'improvement' || n.kind === 'technical_error'),
    strengths: notes.filter((n) => n.kind === 'strength'),
    rewrites: notes.filter((n) => n.kind === 'rewrite'),
    practice: notes.filter((n) => n.kind === 'question'),
    checks,
    about: about(report),
  }
}
