import { useQuery } from '@tanstack/react-query'

import { confirmRole, roleComplete } from '@/features/confirm-role'
import { api } from '@/shared/api'
import type { PrepareIn, PreparationView, RoleProfileData } from '@/shared/api'

export const preparationKey = (id: string) => ['preparation', id] as const

/** A preparation, polled while its documents are analysed. */
export function usePreparation(id: string) {
  return useQuery({
    queryKey: preparationKey(id),
    queryFn: () => api.preparation(id),
    enabled: id !== '',
    refetchInterval: (query) => (query.state.data?.status === 'analysing' ? 1000 : false),
  })
}

/** What still prevents approving a preparation, if anything. */
export type ApprovalBlock = 'analysing' | 'role' | null

/**
 * The analysis has to finish, then the target role has to be complete (approving confirms it)
 * or, without one, the area of a check without a job offer has to be confirmed. `role` holds
 * unconfirmed edits, if any.
 */
export function approvalBlock(
  view: PreparationView | undefined,
  role: RoleProfileData | null,
): ApprovalBlock {
  if (view?.status !== 'review' && view?.status !== 'approved') return 'analysing'
  const current = role ?? view.role_profile
  const missing = current
    ? !roleComplete(current)
    : view.job_mode === 'none' && view.area?.confirmed !== true
  return missing ? 'role' : null
}

/**
 * Approve a reviewed preparation: the target role as shown is confirmed first when it is not
 * yet, then the snapshot is built, or the existing one is kept when nothing changed. Returns the
 * snapshot and the confirmed role.
 */
export async function approvePreparation(
  view: PreparationView,
  role: RoleProfileData | null,
): Promise<{ snapshotId: string; role: RoleProfileData | null }> {
  let current = view
  const shown = role ?? view.role_profile
  if (shown && !shown.confirmed) current = await confirmRole(view, shown)
  const confirmed = current.role_profile ?? null
  if (current.status === 'approved' && current.snapshot_id)
    return { snapshotId: current.snapshot_id, role: confirmed }
  return { snapshotId: (await api.approve(current.id)).id, role: confirmed }
}

/** The same documents and settings, to analyse them again after a failed analysis. */
export function prepareAgain(view: PreparationView): PrepareIn {
  const cv = view.documents.find((d) => d.kind === 'cv')
  const offer = view.documents.find((d) => d.kind === 'job_offer')
  return {
    language: view.language === 'en' ? 'en' : 'it',
    job_mode: view.job_mode as PrepareIn['job_mode'],
    cv_id: cv?.id ?? null,
    job_offer_id: offer?.id ?? null,
    resources: view.documents
      .filter((d) => d.kind === 'resource')
      .map((d) => ({ title: d.title, document_id: d.id })),
    profile_id: view.profile_id,
    execution_profile: view.execution_profile,
  }
}
