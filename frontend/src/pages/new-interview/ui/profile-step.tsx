import { useNavigate } from '@tanstack/react-router'

import { nextStep, stepDone, useDraft } from '@/entities/preparation'
import { ProfilePicker } from '@/features/select-profile'
import { useMessages } from '@/shared/i18n'
import { newInterviewMessages } from './messages'
import { stepPath } from '../model/paths'
import { StepFooter, StepFrame } from './step-frame'

export function ProfileStep() {
  const t = useMessages(newInterviewMessages)
  const navigate = useNavigate()
  const draft = useDraft()
  const done = stepDone(draft, 'resource-profile')
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
          hint={hint}
          onContinue={() => {
            void navigate({ to: stepPath(nextStep(draft, 'resource-profile')) })
          }}
        />
      }
    >
      <ProfilePicker id="resource-profile" choice={draft.profile} onChange={draft.chooseProfile} />
    </StepFrame>
  )
}
