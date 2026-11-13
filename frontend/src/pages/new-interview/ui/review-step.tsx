import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useNavigate } from '@tanstack/react-router'

import { useDraft } from '@/entities/preparation'
import { startAnalysis } from '@/features/edit-documents'
import {
  ContextReview,
  approvalBlock,
  approvePreparation,
  preparationKey,
  useApprovalHint,
  usePreparation,
} from '@/widgets/context-review'
import { useMessages } from '@/shared/i18n'
import { Alert, AlertDescription } from '@/shared/ui/alert'
import { newInterviewMessages } from './messages'
import { stepPath } from '../model/paths'
import { StepFooter, StepFrame } from './step-frame'

export function ReviewStep() {
  const t = useMessages(newInterviewMessages)
  const navigate = useNavigate()
  const client = useQueryClient()
  const draft = useDraft()
  const id = draft.preparationId ?? ''
  const preparation = usePreparation(id)
  const view = preparation.data
  const approve = useMutation({
    mutationFn: () => {
      if (!view) throw new Error('preparation unavailable')
      return approvePreparation(view, draft.roleProfile)
    },
    onSuccess: ({ snapshotId, role }) => {
      draft.setRoleProfile(role)
      draft.setSnapshot(snapshotId)
      void client.invalidateQueries({ queryKey: preparationKey(id) })
      void navigate({ to: stepPath('final-check') })
    },
  })
  const retry = useMutation({
    mutationFn: () => startAnalysis(draft.profile?.kind === 'saved' ? draft.profile.id : null),
  })
  const hint = useApprovalHint(view, draft.roleProfile)
  return (
    <StepFrame
      step="fact-review"
      footer={
        <StepFooter
          step="fact-review"
          label={t.approve}
          disabled={approvalBlock(view, draft.roleProfile) !== null}
          pending={approve.isPending}
          hint={hint}
          onContinue={() => {
            approve.mutate()
          }}
        />
      }
    >
      <ContextReview
        preparation={preparation}
        role={draft.roleProfile}
        onRoleEdit={draft.setRoleProfile}
        onReopened={() => {
          draft.setSnapshot(null)
        }}
        onRetry={() => {
          retry.mutate()
        }}
        retrying={retry.isPending}
      />
      {(approve.error ?? retry.error) && (
        <Alert variant="destructive">
          <AlertDescription>{(approve.error ?? retry.error)?.message}</AlertDescription>
        </Alert>
      )}
    </StepFrame>
  )
}
