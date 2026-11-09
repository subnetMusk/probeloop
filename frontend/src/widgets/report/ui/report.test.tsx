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
