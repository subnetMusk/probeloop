// @vitest-environment jsdom
import { cleanup, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'

import type { RequirementDetailView } from '@/shared/api'
import { setLanguage } from '@/shared/lib/preferences'
import { RequirementDetail } from './requirement-detail'

const DETAIL: RequirementDetailView = {
  obligation: 'must',
  cue: 'Requisiti',
  category: 'experience',
  any_of: [
    { value: 'Python', open: false },
    { value: 'another backend language', open: true },
  ],
  equivalents: [{ kind: 'experience', value: 'equivalent experience' }],
  threshold: { kind: 'years', minimum: '3', subject: 'backend development' },
  refines: null,
  implicit: false,
  disputed: true,
  readings: [
    { source: 'cue', obligation: 'must' },
    { source: 'model', obligation: 'preferred' },
  ],
}

beforeEach(() => {
  setLanguage('en')
})
afterEach(cleanup)

it('shows how binding a requirement is, why, and what satisfies it', () => {
  render(<RequirementDetail id="r1" detail={DETAIL} onObligation={vi.fn()} />)
  const group = screen.getByRole('group', { name: 'How binding' })
  expect(group.querySelector('[aria-pressed="true"]')?.textContent).toBe('Required')
  expect(screen.getByText('from “Requisiti”')).toBeTruthy()
  expect(screen.getByText('Any of: Python, another backend language (or similar)')).toBeTruthy()
  expect(screen.getByText('Or: equivalent experience')).toBeTruthy()
  expect(screen.getByText('At least 3 years of backend development')).toBeTruthy()
  expect(screen.getByRole('note').textContent).toBe(
    'The sources disagree (the offer: required, analysis model: preferred). Choose the right one.',
  )
})

it('lets the user settle the obligation, and says nothing more when the sources agree', async () => {
  const choose = vi.fn()
  render(
    <RequirementDetail
      id="r1"
      detail={{ ...DETAIL, disputed: false, any_of: [], equivalents: [], threshold: null }}
      onObligation={choose}
    />,
  )
  await userEvent.click(screen.getByRole('button', { name: 'Required' }))
  expect(choose).not.toHaveBeenCalled()
  await userEvent.click(screen.getByRole('button', { name: 'Preferred' }))
  expect(choose).toHaveBeenCalledWith('preferred')
  expect(screen.queryByRole('note')).toBeNull()
  expect(screen.queryByRole('list')).toBeNull()
})
