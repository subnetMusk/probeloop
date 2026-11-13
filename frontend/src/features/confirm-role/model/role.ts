import { api } from '@/shared/api'
import type { PreparationView, RoleProfileData } from '@/shared/api'

/** A target role still to be written, for a start without documents. */
export function emptyRole(): RoleProfileData {
  return {
    profession: '',
    target_role: '',
    seniority: '',
    responsibilities: [],
    competencies: [],
    basis_fact_ids: [],
    rationale: '',
    confirmed: false,
  }
}

/** Whether a target role can be confirmed: profession, role and level, within the limits. */
export function roleComplete(role: RoleProfileData): boolean {
  return (
    [role.profession, role.target_role, role.seniority].every((s) => s.trim()) &&
    [...role.responsibilities, ...role.competencies].every((s) => s.length <= 400) &&
    role.responsibilities.filter((s) => s.trim()).length <= 12 &&
    role.competencies.filter((s) => s.trim()).length <= 12
  )
}

/**
 * Save a target role as confirmed. An approved preparation is reopened first, because its
 * snapshot was built on the role as it was.
 */
export async function confirmRole(
  preparation: PreparationView,
  role: RoleProfileData,
): Promise<PreparationView> {
  if (preparation.status === 'approved') await api.reopen(preparation.id)
  return api.setRoleProfile(preparation.id, {
    ...role,
    responsibilities: role.responsibilities.map((s) => s.trim()).filter(Boolean),
    competencies: role.competencies.map((s) => s.trim()).filter(Boolean),
    confirmed: true,
  })
}
