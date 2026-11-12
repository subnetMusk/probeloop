import { useIsMutating } from '@tanstack/react-query'
import { useNavigate } from '@tanstack/react-router'
import { Loader2Icon } from 'lucide-react'

import { useDraft } from '@/entities/preparation'
import {
  DocumentsEditor,
  SaveProfileDialog,
  UPLOAD_KEY,
  documentsMessages,
  problemsOf,
  useCommitDocuments,
  useProblemText,
  useProfileDocuments,
} from '@/features/edit-documents'
import { useMessages } from '@/shared/i18n'
import { Alert, AlertDescription } from '@/shared/ui/alert'
import { newInterviewMessages } from './messages'
import { stepPath } from '../model/paths'
import { StepFooter, StepFrame } from './step-frame'

export function DocumentsStep() {
  const t = useMessages(newInterviewMessages)
  const d = useMessages(documentsMessages)
  const navigate = useNavigate()
  const draft = useDraft()
  const loading = useProfileDocuments(draft.profile)
  const uploads = useIsMutating({ mutationKey: UPLOAD_KEY })
  const describe = useProblemText()
  const { commit, asking, cancel } = useCommitDocuments(() => {
    void navigate({ to: stepPath('fact-review') })
  })
  const problems = problemsOf(draft.documents)
  const hint = uploads
    ? t.missing.uploading
    : problems.length
      ? `${d.problems.intro} ${problems.map(describe).join('; ')}.`
      : undefined
  const execution = draft.settings.execution ?? 'local'
  return (
    <StepFrame
      step="documents"
      required
      footer={
        <StepFooter
          step="documents"
          disabled={loading.loading || uploads > 0 || problems.length > 0}
          pending={commit.isPending}
          hint={hint}
          onContinue={() => {
            commit.mutate(undefined)
          }}
        />
      }
    >
      {loading.loading ? (
        <p className="flex items-center gap-2 text-muted-foreground" aria-live="polite">
          <Loader2Icon className="size-4 animate-spin" aria-hidden="true" />
          {d.loading}
        </p>
      ) : (
        <DocumentsEditor
          id="documents"
          documents={draft.documents}
          language={draft.settings.language}
          execution={execution}
          onChange={draft.updateDocuments}
        />
      )}
      {loading.error && (
        <Alert variant="destructive">
          <AlertDescription>
            {d.loadError} {loading.error.message}
          </AlertDescription>
        </Alert>
      )}
      {commit.error && !asking && (
        <Alert variant="destructive">
          <AlertDescription>{commit.error.message}</AlertDescription>
        </Alert>
      )}
      <SaveProfileDialog
        open={asking}
        profileName={draft.profile?.kind === 'saved' ? draft.profile.name : ''}
        pending={commit.isPending}
        error={commit.error?.message}
        onConfirm={(choice) => {
          commit.mutate(choice)
        }}
        onCancel={cancel}
      />
    </StepFrame>
  )
}
