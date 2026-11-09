import { useNavigate } from '@tanstack/react-router'

import { useDraft } from '@/entities/preparation'
import type { ProfileView } from '@/shared/api'

/** Start a new preparation from a saved profile: its documents load in the documents step. */
export function useStartWithProfile() {
  const navigate = useNavigate()
  return (profile: ProfileView) => {
    const draft = useDraft.getState()
    draft.reset()
    draft.chooseProfile({ kind: 'saved', id: profile.id, name: profile.name })
    void navigate({ to: '/new-interview' })
  }
}
