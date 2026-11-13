import { api } from '@/shared/api'
import type { ProfileView } from '@/shared/api'

/** Start the analysis of a saved profile's documents, as they are, for a CV check. */
export function prepareProfileCheck(
  profile: ProfileView,
  language: 'it' | 'en',
  execution: string,
) {
  return api.prepare({
    language,
    job_mode: profile.job_mode,
    cv_id: profile.cv?.id ?? null,
    job_offer_id: profile.job_offer?.id ?? null,
    resources: profile.resources.map((r) => ({ title: r.title, document_id: r.id })),
    profile_id: profile.id,
    execution_profile: execution,
  })
}
