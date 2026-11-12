import { describe, expect, it } from 'vitest'

import type { PreparationView, RoleProfileData } from '@/shared/api'
import { approvalBlock, prepareAgain } from './preparation'

const role: RoleProfileData = {
  profession: 'Software',
  target_role: 'Backend developer',
  seniority: 'mid',
  responsibilities: [],
  competencies: [],
  basis_fact_ids: [],
  rationale: '',
  confirmed: false,
}

function view(patch: Partial<PreparationView> = {}): PreparationView {
  return {
    id: 'p1',
    status: 'review',
    language: 'en',
    job_mode: 'offer',
    documents: [
      { id: 'cv1', kind: 'cv', title: 'CV' },
      { id: 'jo1', kind: 'job_offer', title: 'Offer' },
      { id: 'r1', kind: 'resource', title: 'Notes' },
    ] as PreparationView['documents'],
    facts: [],
    matches: [],
    area: null,
    vocabulary: [],
    error: null,
    snapshot_id: null,
    created_at: 0,
    profile_id: 'pr1',
    execution_profile: 'cloud',
    analysis: null,
    role_profile: role,
    ...patch,
  }
}

describe('approving a preparation', () => {
  it('waits for the analysis, then for the confirmed role', () => {
    expect(approvalBlock(undefined, null)).toBe('analysing')
    expect(approvalBlock(view({ status: 'analysing' }), null)).toBe('analysing')
    expect(approvalBlock(view({ status: 'failed' }), null)).toBe('analysing')
    expect(approvalBlock(view(), null)).toBe('role')
    expect(approvalBlock(view({ role_profile: { ...role, confirmed: true } }), null)).toBeNull()
    // Unconfirmed edits of the caller count, even over a confirmed role.
    const confirmed = view({ role_profile: { ...role, confirmed: true } })
    expect(approvalBlock(confirmed, { ...role, confirmed: false })).toBe('role')
  })

  it('needs the area of a check without a job offer when there is no role', () => {
    const none = view({ job_mode: 'none', role_profile: null })
    expect(approvalBlock(none, null)).toBe('role')
    const area = { area: 'Backend', seniority: 'mid', confirmed: true } as PreparationView['area']
    expect(approvalBlock({ ...none, area }, null)).toBeNull()
  })

  it('analyses the same documents again', () => {
    expect(prepareAgain(view())).toEqual({
      language: 'en',
      job_mode: 'offer',
      cv_id: 'cv1',
      job_offer_id: 'jo1',
      resources: [{ title: 'Notes', document_id: 'r1' }],
      profile_id: 'pr1',
      execution_profile: 'cloud',
    })
  })
})
