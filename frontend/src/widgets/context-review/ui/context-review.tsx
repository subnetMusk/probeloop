import { useQueryClient } from '@tanstack/react-query'
import type { UseQueryResult } from '@tanstack/react-query'
import { Loader2Icon } from 'lucide-react'

import { RoleProfileEditor } from '@/features/confirm-role'
import { FactReview } from '@/features/review-facts'
import { localizeProblem } from '@/shared/api'
import type { PreparationView, RoleProfileData } from '@/shared/api'
import { useMessages } from '@/shared/i18n'
import { useLanguage } from '@/shared/lib/preferences'
import { Alert, AlertDescription, AlertTitle } from '@/shared/ui/alert'
import { Button } from '@/shared/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/shared/ui/card'
import { Progress } from '@/shared/ui/progress'
import { preparationKey } from '../model/preparation'
import { contextReviewMessages } from './messages'

/**
 * The review of analysed documents: the analysis while it runs, then the target role and the
 * extracted facts. The caller keeps unconfirmed role edits (`role`) and approves.
 */
export function ContextReview({
  preparation,
  role,
  onRoleEdit,
  onReopened,
  onRetry,
  retrying,
}: {
  preparation: UseQueryResult<PreparationView>
  role: RoleProfileData | null
  onRoleEdit: (role: RoleProfileData | null) => void
  /** Called when a change reopened the approved review. */
  onReopened: () => void
  /** Analyse the documents again after a failure. */
  onRetry: () => void
  retrying: boolean
}) {
  const t = useMessages(contextReviewMessages)
  const language = useLanguage()
  const client = useQueryClient()
  const view = preparation.data
  const reviewable = view?.status === 'review' || view?.status === 'approved'
  const store = (updated: PreparationView) => {
    client.setQueryData(preparationKey(updated.id), updated)
  }
  return (
    <>
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
            <Button type="button" variant="outline" disabled={retrying} onClick={onRetry}>
              {t.analysis.retry}
            </Button>
          </AlertDescription>
        </Alert>
      )}
      {view && reviewable && (
        <RoleProfileEditor
          preparation={view}
          role={role}
          onEdit={onRoleEdit}
          onChange={store}
          onReopened={onReopened}
        />
      )}
      {view && reviewable && view.documents.length > 0 && (
        <FactReview
          preparation={view}
          onChange={(updated) => {
            store(updated)
            // Facts change the basis of the role; unconfirmed edits keep their own text.
            if (role?.confirmed !== false) onRoleEdit(updated.role_profile ?? null)
            else if (updated.role_profile)
              onRoleEdit({ ...role, basis_fact_ids: updated.role_profile.basis_fact_ids })
          }}
          onReopened={onReopened}
        />
      )}
    </>
  )
}
