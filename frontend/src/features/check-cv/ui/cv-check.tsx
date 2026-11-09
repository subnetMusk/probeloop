import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Link } from '@tanstack/react-router'
import { FileCheckIcon, Loader2Icon } from 'lucide-react'
import { useEffect } from 'react'

import { RequirementList } from '@/entities/preparation'
import { rememberReportJob } from '@/entities/report-job'
import { api, isRunning } from '@/shared/api'
import type { ExecutionProfile, JobView } from '@/shared/api'
import { defineMessages, localise, useMessages } from '@/shared/i18n'
import { Button } from '@/shared/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/shared/ui/card'
import { score } from '@/shared/lib/format'
import { useLanguage } from '@/shared/lib/preferences'
import { Progress } from '@/shared/ui/progress'

const messages = defineMessages({
  en: {
    title: 'CV check',
    description: (offer: boolean) =>
      offer
        ? 'How your CV reads against the job offer. Optional: you can start the interview without it.'
        : 'How your CV reads to a recruiter. Optional: you can start the interview without it.',
    noCv: 'There is no CV in the documents, so there is nothing to check.',
    run: 'Check the CV',
    again: 'Check again',
    running: 'Checking the CV',
    score: (overall: string) => `Overall ${overall} / 5`,
    unavailable: 'Not enough evidence for an overall score',
    criteria: (assessed: number, total: number) =>
      `${String(assessed)} of ${String(total)} criteria assessable`,
    version: (version: number) => `version ${String(version)}`,
    open: 'Open the full CV report',
    requirements: 'Job requirements',
  },
  it: {
    title: 'Controllo del CV',
    description: (offer: boolean) =>
      offer
        ? 'Come si legge il tuo CV rispetto all’offerta. Facoltativo: puoi iniziare il colloquio anche senza.'
        : 'Come si legge il tuo CV agli occhi di un selezionatore. Facoltativo: puoi iniziare il colloquio anche senza.',
    noCv: 'Tra i documenti non c’è un CV, quindi non c’è nulla da controllare.',
    run: 'Controlla il CV',
    again: 'Controlla di nuovo',
    running: 'Controllo del CV in corso',
    score: (overall: string) => `Complessivo ${overall} / 5`,
    unavailable: 'Evidenze insufficienti per un voto complessivo',
    criteria: (assessed: number, total: number) =>
      `${String(assessed)} criteri valutabili su ${String(total)}`,
    version: (version: number) => `versione ${String(version)}`,
    open: 'Apri il report completo del CV',
    requirements: 'Requisiti della posizione',
  },
})

/**
 * Review the CV of an approved context, against its job offer when there is one. Each run keeps
 * the earlier versions; the latest is summarised here and opens in full on its own page.
 */
export function CvCheck({
  snapshotId,
  language,
  execution,
  onBusyChange,
}: {
  snapshotId: string
  language: 'it' | 'en'
  execution: ExecutionProfile
  onBusyChange: (busy: boolean) => void
}) {
  const t = useMessages(messages)
  const ui = useLanguage()
  const client = useQueryClient()
  const reportsKey = ['cv-reviews', snapshotId]
  const jobsKey = ['cv-jobs', snapshotId]
  const snapshot = useQuery({
    queryKey: ['snapshot', snapshotId],
    queryFn: () => api.snapshot(snapshotId),
    staleTime: Infinity,
  })
  const jobs = useQuery({
    queryKey: jobsKey,
    queryFn: async () => {
      const list = await api.snapshotJobs(snapshotId)
      const previous = client.getQueryData<JobView[]>(jobsKey)
      if (previous?.some(isRunning) && !list.some(isRunning))
        void client.invalidateQueries({ queryKey: reportsKey })
      return list
    },
    refetchInterval: (query) => (query.state.data?.some(isRunning) ? 1500 : false),
  })
  const reports = useQuery({ queryKey: reportsKey, queryFn: () => api.cvReviews(snapshotId) })
  const job = jobs.data?.filter((j) => j.kind === 'review_cv').at(-1)
  const running = isRunning(job)
  const start = useMutation({
    mutationFn: () => api.reviewCv(snapshotId, language, execution),
    onSuccess: (created) => {
      rememberReportJob(created.id)
      client.setQueryData<JobView[]>(jobsKey, (old) => [...(old ?? []), created])
      void client.invalidateQueries({ queryKey: jobsKey })
    },
  })
  useEffect(() => {
    onBusyChange(running || start.isPending)
  }, [running, start.isPending, onBusyChange])

  const hasCv = snapshot.data?.documents.some((d) => d.kind === 'cv') ?? false
  const hasOffer = snapshot.data !== undefined && snapshot.data.job_mode !== 'none'
  const latest = reports.data?.at(-1)
  return (
    <Card data-testid="cv-check">
      <CardHeader>
        <CardTitle role="heading" aria-level={2} className="flex items-center gap-2">
          <FileCheckIcon className="size-5 text-brand-text" aria-hidden="true" />
          {t.title}
        </CardTitle>
        <CardDescription>{t.description(hasOffer)}</CardDescription>
      </CardHeader>
      <CardContent className="flex flex-col gap-4">
        {snapshot.data && !hasCv && <p className="text-muted-foreground">{t.noCv}</p>}
        {latest && (
          <div className="flex flex-col gap-1 rounded-lg bg-muted/50 p-4" data-testid="cv-score">
            <p className="font-heading text-2xl font-semibold">
              {latest.overall === null ? t.unavailable : t.score(score(latest.overall, ui))}
            </p>
            <p className="text-sm text-muted-foreground">
              {t.criteria(latest.assessed, latest.criteria)} · {t.version(latest.version)}
            </p>
            <Link
              to="/cv-checks/$snapshotId/reports/$reportId"
              params={{ snapshotId, reportId: latest.id }}
              className="mt-1 self-start text-sm text-brand-text underline"
            >
              {t.open}
            </Link>
          </div>
        )}
        {running && job && (
          <div aria-live="polite" className="flex flex-col gap-2">
            <p className="flex items-center gap-2 text-sm">
              <Loader2Icon className="size-4 animate-spin" aria-hidden="true" />
              {t.running}
              {job.message ? `: ${localise(job.message)}` : ''}
            </p>
            <Progress value={job.progress * 100} />
          </div>
        )}
        {job?.status === 'failed' && job.error && (
          <p role="alert" className="text-sm text-destructive">
            {localise(job.error)}
          </p>
        )}
        {hasCv && (
          <Button
            type="button"
            variant={latest ? 'outline' : 'default'}
            className="self-start"
            disabled={running || start.isPending}
            onClick={() => {
              start.mutate()
            }}
          >
            {latest ? t.again : t.run}
          </Button>
        )}
        {(start.error ?? reports.error ?? snapshot.error) && (
          <p role="alert" className="text-sm text-destructive">
            {(start.error ?? reports.error ?? snapshot.error)?.message}
          </p>
        )}
        {hasOffer && (
          <section aria-labelledby="cv-check-requirements" className="flex flex-col gap-1">
            <h3 id="cv-check-requirements" className="text-sm font-medium text-muted-foreground">
              {t.requirements}
            </h3>
            <RequirementList requirements={snapshot.data.requirements} />
          </section>
        )}
      </CardContent>
    </Card>
  )
}
