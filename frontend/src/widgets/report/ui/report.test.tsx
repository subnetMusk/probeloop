// @vitest-environment jsdom
/// <reference types="node" />
import { readFileSync } from 'node:fs'
import { cleanup, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, expect, it } from 'vitest'

import { toCvReportView, toInterviewReportView } from '@/entities/report'
import type { ReportData, SessionView } from '@/shared/api'
import { setLanguage } from '@/shared/lib/preferences'
import { CvReport } from './cv-report'
import { InterviewReport } from './interview-report'

const fixture = JSON.parse(
  readFileSync('../backend/tests/fixtures/synthetic/assessment/report-outline.json', 'utf8'),
) as Record<'interview' | 'cv', { report: ReportData; session?: SessionView }>
beforeEach(() => {
  setLanguage('en')
})
afterEach(cleanup)

it('renders interview sections in export order and links quotes to frozen answers', async () => {
  const view = toInterviewReportView(fixture.interview.report, fixture.interview.session)
  const { container } = render(<InterviewReport view={view} />)
  expect([...container.children].map((element) => element.id).filter(Boolean)).toEqual(
    view.sections,
  )
  expect(screen.getAllByText('Kafka non garantisce l’ordine tra partizioni.')).toHaveLength(1)
  expect(screen.getByText('Partizioni per cliente.').textContent).toBe('Partizioni per cliente.')
  expect(screen.queryByText('Ultima versione.')).toBeNull()
  expect(screen.getAllByRole('link', { name: 'Answer 2' })[0]?.getAttribute('href')).toBe(
    '#answer-3',
  )
  expect(container.querySelector('#answer-3')?.textContent).toContain('Partizioni per cliente.')
  expect(screen.getByText('63%')).toBeTruthy()
  const technical = container.querySelector<HTMLDetailsElement>('#technical')
  expect(technical?.open).toBe(false)
  await userEvent.click(screen.getByText('Technical details'))
  expect(technical?.open).toBe(true)
})

it('keeps CV checks in priority order and matches the export sections', () => {
  const view = toCvReportView(fixture.cv.report)
  const { container } = render(<CvReport view={view} />)
  expect([...container.children].map((element) => element.id).filter(Boolean)).toEqual(
    view.sections,
  )
  const checks = [...container.querySelectorAll('#checks li')].map((element) => element.textContent)
  expect(checks).toEqual([
    expect.stringContaining('Synthetic review check.'),
    expect.stringContaining('Synthetic information check.'),
    expect.stringContaining('Synthetic passed check.'),
    expect.stringContaining('Synthetic unassessable check.'),
  ])
  expect(screen.getAllByText('Reduced processing time by 20%.')).toHaveLength(1)
})

it('shows an unavailable overall score without inventing a midpoint', () => {
  const view = toCvReportView({ ...fixture.cv.report, overall: null, observations: [] })
  render(<CvReport view={view} />)
  expect(screen.getByText('Not enough evidence for an overall score')).toBeTruthy()
  expect(screen.queryByText('Developing')).toBeNull()
})

it('shows the lowest observed score as zero and exposes recorded assistance', async () => {
  const view = toInterviewReportView(
    { ...fixture.interview.report, scale: '0_100', overall: 0 },
    fixture.interview.session,
  )
  view.target = 'Economics · Analyst · Junior'
  const unit = view.units[0]
  if (!unit) throw new Error('fixture needs a unit')
  unit.assistance = [
    { purpose: 'clarification', level: 0, text: 'Use the GDP deflator.' },
    { purpose: 'hint', level: 1, text: 'Compare the two factors.' },
  ]
  render(<InterviewReport view={view} />)
  expect(screen.getByRole('region', { name: 'Overall score' }).textContent).toContain('0/ 100')
  expect(screen.getByText(view.target)).toBeTruthy()
  await userEvent.click(screen.getByText('Assistance during this exchange'))
  expect(screen.getByText('Hint 1')).toBeTruthy()
  expect(screen.getByText('Use the GDP deflator.')).toBeTruthy()
})

it('does not call feedback absent when only the generated summary is missing', () => {
  const view = toCvReportView({
    ...fixture.cv.report,
    observations: fixture.cv.report.observations.filter((note) => note.kind !== 'summary'),
  })
  render(<CvReport view={view} />)
  const hero = screen.getByRole('region', { name: 'Overall score' })
  expect(hero.textContent).toContain('Explore the evidence and feedback below.')
  expect(hero.textContent).not.toContain('No evidence-backed observations.')
})
