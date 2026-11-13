import { afterEach, describe, expect, it, vi } from 'vitest'

import { api } from '@/shared/api'
import type { PreparationView, RoleProfileData } from '@/shared/api'
import { approvalBlock, approvePreparation, prepareAgain } from './preparation'

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
  it('waits for the analysis, then for a complete role, which approving confirms', () => {
    expect(approvalBlock(undefined, null)).toBe('analysing')
    expect(approvalBlock(view({ status: 'analysing' }), null)).toBe('analysing')
    expect(approvalBlock(view({ status: 'failed' }), null)).toBe('analysing')
    // An unconfirmed but complete role does not block: approving confirms it.
    expect(approvalBlock(view(), null)).toBeNull()
    expect(approvalBlock(view({ role_profile: { ...role, confirmed: true } }), null)).toBeNull()
    // The caller's unconfirmed edits count, even over a confirmed role.
    const confirmed = view({ role_profile: { ...role, confirmed: true } })
    expect(approvalBlock(confirmed, { ...role, seniority: ' ', confirmed: false })).toBe('role')
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

describe('approvePreparation', () => {
  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('confirms the role as shown, then approves', async () => {
    const edited = { ...role, seniority: 'senior' }
    const setRole = vi
      .spyOn(api, 'setRoleProfile')
      .mockResolvedValue(view({ role_profile: { ...edited, confirmed: true } }))
    const approve = vi.spyOn(api, 'approve').mockResolvedValue({ id: 's1' } as never)
    const result = await approvePreparation(view(), edited)
    expect(setRole).toHaveBeenCalledWith('p1', { ...edited, confirmed: true })
    expect(approve).toHaveBeenCalledWith('p1')
    expect(result).toEqual({ snapshotId: 's1', role: { ...edited, confirmed: true } })
  })

  it('reopens an approved preparation whose role was edited', async () => {
    const reopen = vi.spyOn(api, 'reopen').mockResolvedValue(undefined as never)
    vi.spyOn(api, 'setRoleProfile').mockResolvedValue(
      view({ status: 'review', role_profile: { ...role, confirmed: true } }),
    )
    vi.spyOn(api, 'approve').mockResolvedValue({ id: 's2' } as never)
    const approved = view({ status: 'approved', snapshot_id: 's1' })
    const result = await approvePreparation(approved, { ...role, confirmed: false })
    expect(reopen).toHaveBeenCalledWith('p1')
    expect(result.snapshotId).toBe('s2')
  })

  it('keeps the snapshot of an approved preparation with a confirmed role', async () => {
    const setRole = vi.spyOn(api, 'setRoleProfile')
    const approve = vi.spyOn(api, 'approve')
    const approved = view({
      status: 'approved',
      snapshot_id: 's1',
      role_profile: { ...role, confirmed: true },
    })
    expect((await approvePreparation(approved, null)).snapshotId).toBe('s1')
    expect(setRole).not.toHaveBeenCalled()
    expect(approve).not.toHaveBeenCalled()
  })
})
