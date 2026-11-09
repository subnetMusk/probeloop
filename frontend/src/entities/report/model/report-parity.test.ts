/// <reference types="node" />
import { readFileSync } from 'node:fs'
import { expect, it } from 'vitest'

import type { ReportData, SessionView } from '@/shared/api'
import { toCvReportView, toInterviewReportView } from './report-view'
import type { CriterionView, NoteView, QuoteView } from './report-view'

const outlineFixture = JSON.parse(
  readFileSync(
    new URL(
      '../../../../../backend/tests/fixtures/synthetic/assessment/report-outline.json',
      import.meta.url,
    ),
    'utf8',
  ),
) as Record<'interview' | 'cv', { report: ReportData; session?: SessionView; expected: unknown }>

const quote = (q: QuoteView) => ({ text: q.text, answer: q.answer })
const note = (n: NoteView) => ({
  kind: n.kind,
  text: n.text,
  replacement: n.replacement,
  quotes: n.quotes.map(quote),
  unit: n.unit,
})
const criterion = (c: CriterionView) => ({
  id: c.id,
  label: c.label,
  value: c.value,
  reason: c.reason,
  unstable: c.unstable,
  quotes: c.quotes.map(quote),
})

for (const kind of ['interview', 'cv'] as const) {
  it(`${kind} view matches the shared export outline`, () => {
    const fixture = outlineFixture[kind]
    const view =
      kind === 'interview'
        ? toInterviewReportView(fixture.report, fixture.session)
        : toCvReportView(fixture.report)
    const interview = 'units' in view ? view : null
    const cv = 'checks' in view ? view : null
    const delivery = interview?.delivery
    const about = view.about
    expect({
      sections: view.sections,
      overall: view.overall,
      band: view.band,
      assessed: view.assessed,
      criteria_count: view.criteriaCount,
      summary: view.summary ? note(view.summary) : null,
      improvements: view.improvements.map(note),
      strengths: view.strengths.map(note),
      rewrites: cv?.rewrites.map(note) ?? [],
      practice: view.practice.map(note),
      criteria: view.criteria.map(criterion),
      units:
        interview?.units.map((unit) => ({
          number: unit.number,
          kind: unit.kind,
          scored: unit.scored,
          questions: unit.questions.map((q) => q.text),
          answers: unit.answers.map((a) => ({ number: a.number, text: a.text })),
          scores: unit.scores.map(criterion),
        })) ?? [],
      requirements:
        interview?.requirements.map((row) => ({ ...row, quotes: row.quotes.map(quote) })) ?? [],
      checks: cv?.checks.map((check) => ({ ...check, quotes: check.quotes.map(quote) })) ?? [],
      delivery: delivery
        ? {
            median_rate: delivery.medianRate,
            median_latency: delivery.medianLatency,
            fillers_per_minute: delivery.fillersPerMinute,
            long_pauses: delivery.longPauses,
            talk_share: delivery.talkShare,
            budget_share: delivery.budgetShare,
            per_answer: delivery.perAnswer.map((a) => ({
              answer: a.answer,
              duration: a.duration,
              rate: a.rate,
              fillers: a.fillers,
              pauses: a.pauses,
              latency: a.latency,
            })),
          }
        : null,
      technical: {
        model: about.model,
        prompt: about.prompt,
        rubric: about.rubric,
        rubric_hash: about.rubricHash,
        fingerprint: about.fingerprint,
        dropped: about.dropped,
        edited_answers: about.editedAnswers,
        duration_s: about.durationS,
        disclaimer: about.disclaimer,
      },
      unstable: [...view.criteria, ...(interview?.units.flatMap((u) => u.scores) ?? [])].some(
        (c) => c.unstable,
      ),
    }).toEqual(fixture.expected)
  })
}
