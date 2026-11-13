import { useNavigate } from '@tanstack/react-router'
import { useMutation } from '@tanstack/react-query'

import { nextStep, stepDone, useDraft, preparationKeyOf, getDraft } from '@/entities/preparation'
import { RoleProfileEditor, emptyRole, roleComplete } from '@/features/confirm-role'
import { ProfilePicker } from '@/features/select-profile'
import { startAnalysis } from '@/features/edit-documents'
import { approvePreparation } from '@/widgets/context-review'
import { api } from '@/shared/api'
import { Alert, AlertDescription } from '@/shared/ui/alert'
import { useMessages } from '@/shared/i18n'
import { newInterviewMessages } from './messages'
import { stepPath } from '../model/paths'
import { StepFooter, StepFrame } from './step-frame'

/**
 * Prepare a start without documents: an empty preparation, analysed at once, with the role
 * written here confirmed and approved.
 */
async function prepareQuickStart(): Promise<void> {
  const draft = getDraft()
  if (draft.preparationId === null || draft.preparationKey !== preparationKeyOf(draft))
    await startAnalysis(null)
  const id = getDraft().preparationId
  if (id === null) throw new Error('preparation unavailable')
  const view = await api.preparation(id)
  if (view.status !== 'review' && view.status !== 'approved')
    throw new Error('preparation unavailable')
  const { snapshotId, role } = await approvePreparation(view, getDraft().roleProfile)
  const actions = useDraft.getState()
  actions.setRoleProfile(role)
  actions.setSnapshot(snapshotId)
}

export function ProfileStep() {
  const t = useMessages(newInterviewMessages)
  const navigate = useNavigate()
  const draft = useDraft()
  const quick = draft.profile?.kind === 'quick'
  const role = draft.roleProfile ?? emptyRole()
  // A quick start is ready to continue once its role is complete; continuing approves it.
  const ready = quick ? roleComplete(role) : stepDone(draft, 'resource-profile')
  const proceed = useMutation({
    mutationFn: async () => {
      if (getDraft().profile?.kind === 'quick') await prepareQuickStart()
    },
    onSuccess: () => {
      void navigate({ to: stepPath(nextStep(getDraft(), 'resource-profile')) })
    },
  })
  const hint = ready
    ? undefined
    : quick
      ? t.missing.role
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
          disabled={!ready}
          pending={proceed.isPending}
          hint={hint}
          onContinue={() => {
            proceed.mutate()
          }}
        />
      }
    >
      <ProfilePicker id="resource-profile" choice={draft.profile} onChange={draft.chooseProfile} />
      {quick && <RoleProfileEditor role={role} onEdit={draft.setRoleProfile} />}
      {proceed.error && (
        <Alert variant="destructive">
          <AlertDescription>{proceed.error.message}</AlertDescription>
        </Alert>
      )}
    </StepFrame>
  )
}
