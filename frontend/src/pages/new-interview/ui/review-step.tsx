import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useNavigate } from '@tanstack/react-router'
import { Loader2Icon } from 'lucide-react'

import { useDraft } from '@/entities/preparation'
import { startAnalysis } from '@/features/edit-documents'
import { FactReview } from '@/features/review-facts'
import { api, localizeProblem } from '@/shared/api'
import type { PreparationView } from '@/shared/api'
import { useMessages } from '@/shared/i18n'
import { useLanguage } from '@/shared/lib/preferences'
import { Alert, AlertDescription, AlertTitle } from '@/shared/ui/alert'
import { Button } from '@/shared/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/shared/ui/card'
import { Progress } from '@/shared/ui/progress'
import { newInterviewMessages } from './messages'
import { stepPath } from '../model/paths'
import { StepFooter, StepFrame } from './step-frame'

export function ReviewStep() {
  const language = useLanguage()
  const t = useMessages(newInterviewMessages)
  const navigate = useNavigate()
  const client = useQueryClient()
  const draft = useDraft()
  const id = draft.preparationId ?? ''
  const key = ['preparation', id]
  const preparation = useQuery({
    queryKey: key,
    queryFn: () => api.preparation(id),
    enabled: id !== '',
    refetchInterval: (query) => (query.state.data?.status === 'analysing' ? 1000 : false),
  })
  const view = preparation.data
  const toCheck = () => void navigate({ to: stepPath('final-check') })
  const approve = useMutation({
    mutationFn: async () => {
      if (view?.status === 'approved' && view.snapshot_id) return view.snapshot_id
      return (await api.approve(id)).id
    },
    onSuccess: (snapshotId) => {
      draft.setSnapshot(snapshotId)
      void client.invalidateQueries({ queryKey: key })
      toCheck()
    },
  })
  const retry = useMutation({
    mutationFn: () => startAnalysis(draft.profile?.kind === 'saved' ? draft.profile.id : null),
  })
  const reviewable = view?.status === 'review' || view?.status === 'approved'
  const areaMissing = view?.job_mode === 'none' && view.area?.confirmed !== true
  const hint = !reviewable ? t.missing.analysing : areaMissing ? t.missing.area : undefined
  return (
    <StepFrame
      step="fact-review"
      footer={
        <StepFooter
          step="fact-review"
          label={t.approve}
          disabled={!reviewable || areaMissing}
          pending={approve.isPending}
          hint={hint}
          onContinue={() => {
            approve.mutate()
          }}
        />
      }
    >
      {(preparation.isPending || view?.status === 'analysing') && (
        <Card>
          <CardHeader>
            <CardTitle role="heading" aria-level={2} className="flex items-center gap-2">
              <Loader2Icon className="size-5 animate-spin" aria-hidden="true" />
              {t.analysis.title}
            </CardTitle>
          </CardHeader>
          <CardContent className="flex flex-col gap-3" aria-live="polite">
            <Progress value={(view?.analysis?.progress ?? 0) * 100} />
            <p>
              {view?.analysis?.message
                ? localizeProblem(view.analysis.message, language)
                : t.analysis.waiting}
            </p>
            <p className="text-sm text-muted-foreground">{t.analysis.leave}</p>
          </CardContent>
        </Card>
      )}
      {(preparation.error ?? view?.status === 'failed') && (
        <Alert variant="destructive">
          <AlertTitle>{t.analysis.failed}</AlertTitle>
          <AlertDescription className="flex flex-col items-start gap-3">
            <span>
              {preparation.error?.message ??
                (view?.error ? localizeProblem(view.error, language) : null)}
            </span>
            <Button
              type="button"
              variant="outline"
              disabled={retry.isPending}
              onClick={() => {
                retry.mutate()
              }}
            >
              {t.analysis.retry}
            </Button>
          </AlertDescription>
        </Alert>
      )}
      {view && reviewable && (
        <FactReview
          preparation={view}
          onChange={(updated: PreparationView) => {
            client.setQueryData(key, updated)
          }}
          onReopened={() => {
            draft.setSnapshot(null)
          }}
        />
      )}
      {(approve.error ?? retry.error) && (
        <Alert variant="destructive">
          <AlertDescription>{(approve.error ?? retry.error)?.message}</AlertDescription>
        </Alert>
      )}
    </StepFrame>
  )
}
