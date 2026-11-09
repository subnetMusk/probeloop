// @vitest-environment jsdom
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { cleanup, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'

import { useDraft } from '@/entities/preparation'
import type { PreparationView } from '@/shared/api'
import { setLanguage } from '@/shared/lib/preferences'
import { RoleProfileEditor } from './role-profile-editor'

beforeEach(() => {
  setLanguage('en')
  useDraft.getState().reset()
})
afterEach(cleanup)

const preparation: PreparationView = {
  id: 'synthetic-no-docs',
  status: 'review',
  language: 'en',
  job_mode: 'none',
  documents: [],
  facts: [],
  matches: [],
  area: null,
  vocabulary: [],
  error: null,
  snapshot_id: null,
  created_at: 0,
  profile_id: null,
  execution_profile: 'local',
  analysis: null,
  role_profile: {
    profession: '',
    target_role: '',
    seniority: '',
    responsibilities: [],
    competencies: [],
    basis_fact_ids: [],
    rationale: '',
    confirmed: false,
  },
}

it('requires role and level and keeps unfinished edits when remounted', async () => {
  const client = new QueryClient()
  const show = () =>
    render(
      <QueryClientProvider client={client}>
        <RoleProfileEditor preparation={preparation} onChange={vi.fn()} />
      </QueryClientProvider>,
    )
  const view = show()
  const confirm = screen.getByRole<HTMLButtonElement>('button', { name: 'Confirm role and level' })
  expect(confirm.disabled).toBe(true)
  await userEvent.type(screen.getByRole('textbox', { name: 'Profession or field' }), 'Economics')
  await userEvent.type(
    screen.getByRole('textbox', { name: /^Target role$/ }),
    'Research economist',
  )
  expect(confirm.disabled).toBe(true)
  view.unmount()
  show()
  expect(
    screen.getByRole<HTMLInputElement>('textbox', { name: /^Target role$/ }).value,
  ).toBe('Research economist')
  await userEvent.type(
    screen.getByRole('textbox', { name: 'Target level or training grade' }),
    'Junior under supervision',
  )
  expect(
    screen.getByRole<HTMLButtonElement>('button', { name: 'Confirm role and level' }).disabled,
  ).toBe(false)
  expect(useDraft.getState().roleProfile?.confirmed).toBe(false)
})
