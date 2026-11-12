import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useNavigate, useParams } from '@tanstack/react-router'
import { useState } from 'react'

import { rememberReportJob } from '@/entities/report-job'
import {
  ContextReview,
  approvalBlock,
  prepareAgain,
  useApprovalHint,
  usePreparation,
} from '@/widgets/context-review'
import { api } from '@/shared/api'
import type { RoleProfileData } from '@/shared/api'
import { useMessages } from '@/shared/i18n'
import { useLanguage } from '@/shared/lib/preferences'
import { Alert, AlertDescription } from '@/shared/ui/alert'
import { Button } from '@/shared/ui/button'
import { Page, PageHeader } from '@/shared/ui/page-header'
import { newCvCheckMessages } from './messages'

/** Review the analysis of the documents, then approve them and check the CV. */
export function CvCheckReviewPage() {
  const t = useMessages(newCvCheckMessages)
  const language = useLanguage()
  const navigate = useNavigate()
  const client = useQueryClient()
  const { preparationId } = useParams({ from: '/cv-checks/new/$preparationId' })
  const preparation = usePreparation(preparationId)
  const execution = useQuery({ queryKey: ['execution-profile'], queryFn: api.executionProfile })
  const [role, setRole] = useState<RoleProfileData | null>(null)
  const view = preparation.data
  const check = useMutation({
    mutationFn: async () => {
      if (!view) throw new Error('preparation unavailable')
      const snapshotId =
        view.status === 'approved' && view.snapshot_id
          ? view.snapshot_id
          : (await api.approve(view.id)).id
      const job = await api.reviewCv(
        snapshotId,
        language,
        execution.data?.profile ?? 'local',
        view.profile_id,
      )
      rememberReportJob(job.id)
      return snapshotId
    },
    onSuccess: (snapshotId) => {
      void client.invalidateQueries({ queryKey: ['history'] })
      void navigate({ to: '/cv-checks/$snapshotId', params: { snapshotId }, replace: true })
    },
  })
  const retry = useMutation({
    mutationFn: async () => {
      if (!view) throw new Error('preparation unavailable')
      return api.prepare(prepareAgain(view))
    },
    onSuccess: (again) => {
      setRole(null)
      void navigate({
        to: '/cv-checks/new/$preparationId',
        params: { preparationId: again.id },
        replace: true,
      })
    },
  })
  const noCv = view !== undefined && !view.documents.some((d) => d.kind === 'cv')
  const hint = useApprovalHint(view, role)
  return (
    <Page>
      <PageHeader eyebrow={t.eyebrow} title={t.review.title} description={t.review.description} />
      {noCv ? (
        <p role="alert">{t.review.noCv}</p>
      ) : (
        <ContextReview
          preparation={preparation}
          role={role}
          onRoleEdit={setRole}
          onReopened={() => undefined}
          onRetry={() => {
            retry.mutate()
          }}
          retrying={retry.isPending}
        />
      )}
      {(check.error ?? retry.error) && (
        <Alert variant="destructive">
          <AlertDescription>{(check.error ?? retry.error)?.message}</AlertDescription>
        </Alert>
      )}
      <div className="sticky bottom-0 z-10 -mx-6 flex flex-wrap items-center justify-between gap-3 border-t bg-background/95 px-6 py-4 backdrop-blur">
        <p className="text-sm text-muted-foreground" aria-live="polite">
          {hint}
        </p>
        <Button
          type="button"
          disabled={
            noCv ||
            check.isPending ||
            approvalBlock(view, role) !== null ||
            execution.data === undefined
          }
          onClick={() => {
            check.mutate()
          }}
        >
          {check.isPending ? t.review.approving : t.review.approve}
        </Button>
      </div>
    </Page>
  )
}
