import { useNavigate } from '@tanstack/react-router'
import { useMutation } from '@tanstack/react-query'

import { nextStep, stepDone, useDraft, preparationKeyOf } from '@/entities/preparation'
import { ProfilePicker } from '@/features/select-profile'
import { startAnalysis } from '@/features/edit-documents'
import { Alert, AlertDescription } from '@/shared/ui/alert'
import { useMessages } from '@/shared/i18n'
import { newInterviewMessages } from './messages'
import { stepPath } from '../model/paths'
import { StepFooter, StepFrame } from './step-frame'

export function ProfileStep() {
  const t = useMessages(newInterviewMessages)
  const navigate = useNavigate()
  const draft = useDraft()
  const done = stepDone(draft, 'resource-profile')
  const proceed = useMutation({
    mutationFn: async () => {
      if (
        draft.profile?.kind === 'quick' &&
        (draft.preparationId === null || draft.preparationKey !== preparationKeyOf(draft))
      )
        await startAnalysis(null)
    },
    onSuccess: () => {
      void navigate({ to: stepPath(nextStep(draft, 'resource-profile')) })
    },
  })
  const hint = done
    ? undefined
    : draft.profile?.kind === 'new'
      ? t.missing.profileName
      : t.missing.profile
  return (
    <StepFrame
      step="resource-profile"
      required
      footer={
        <StepFooter
          step="resource-profile"
          disabled={!done}
          pending={proceed.isPending}
          hint={hint}
          onContinue={() => {
            proceed.mutate()
          }}
        />
      }
    >
      <ProfilePicker id="resource-profile" choice={draft.profile} onChange={draft.chooseProfile} />
      {proceed.error && (
        <Alert variant="destructive">
          <AlertDescription>{proceed.error.message}</AlertDescription>
        </Alert>
      )}
    </StepFrame>
  )
}
