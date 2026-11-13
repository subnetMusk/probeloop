// @vitest-environment jsdom
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { cleanup, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, expect, it } from 'vitest'

import type { PreparationView, RoleProfileData } from '@/shared/api'
import { setLanguage } from '@/shared/lib/preferences'
import { roleComplete } from '../model/role'
import { RoleProfileEditor } from './role-profile-editor'

beforeEach(() => {
  setLanguage('en')
})
afterEach(cleanup)

const role = (seniority: string): RoleProfileData => ({
  profession: '',
  target_role: '',
  seniority,
  responsibilities: [],
  competencies: [],
  basis_fact_ids: [],
  rationale: '',
  confirmed: false,
})

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
  role_profile: role(''),
}

it('leaves unfinished edits to the caller, who confirms them on approval', async () => {
  const client = new QueryClient()
  // The caller's store of unconfirmed edits, as the interview draft keeps them.
  let kept: RoleProfileData | null = null
  const current = (): RoleProfileData | null => kept
  let view: ReturnType<typeof render> | undefined
  const element = () => (
    <QueryClientProvider client={client}>
      <RoleProfileEditor
        preparation={preparation}
        role={kept}
        onEdit={(role) => {
          kept = role
          view?.rerender(element())
        }}
      />
    </QueryClientProvider>
  )
  const show = () => render(element())
  view = show()
  expect(screen.queryByRole('button')).toBeNull()
  await userEvent.type(screen.getByRole('textbox', { name: 'Profession or field' }), 'Economics')
  await userEvent.type(screen.getByRole('textbox', { name: /^Target role$/ }), 'Research economist')
  expect(current()?.target_role).toBe('Research economist')
  expect(roleComplete(current() ?? role(''))).toBe(false)
  view.unmount()
  view = show()
  expect(screen.getByRole<HTMLInputElement>('textbox', { name: /^Target role$/ }).value).toBe(
    'Research economist',
  )
  await userEvent.type(
    screen.getByRole('textbox', { name: 'Target level or training grade' }),
    'Junior under supervision',
  )
  expect(roleComplete(current() ?? role(''))).toBe(true)
  expect(current()?.confirmed).toBe(false)
  expect(screen.queryByText('Confirmed')).toBeNull()
})
