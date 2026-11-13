import { useMutation } from '@tanstack/react-query'
import { useNavigate } from '@tanstack/react-router'

import { getDraft, resetDraft, settingsSchema } from '@/entities/preparation'
import { api } from '@/shared/api'

/**
 * Create the interview from the draft and join its call. The draft is cleared and the call
 * replaces the current page, so the browser's Back does not return to a finished preparation.
 */
export function useStartInterview() {
  const navigate = useNavigate()
  return useMutation({
    mutationFn: () => {
      const draft = getDraft()
      const settings = settingsSchema.parse(draft.settings)
      return api.createSession({
        interview_type: settings.interviewType,
        difficulty: settings.difficulty,
        language: settings.language,
        modality: 'voice',
        duration_minutes: settings.minutes,
        snapshot_id: draft.snapshotId,
        execution_profile: settings.execution,
        profile_id:
          draft.profile?.kind === 'saved'
            ? draft.profile.id
            : draft.profile?.kind === 'approved'
              ? draft.profile.profileId
              : null,
      })
    },
    onSuccess: (session) => {
      resetDraft()
      void navigate({
        to: '/live-interview/$sessionId',
        params: { sessionId: session.id },
        replace: true,
      })
    },
  })
}
