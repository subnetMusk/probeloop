import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Link } from '@tanstack/react-router'
import { ExternalLinkIcon, FileCheckIcon, Loader2Icon } from 'lucide-react'
import { useEffect } from 'react'

import { rememberReportJob } from '@/entities/report-job'
import { api, isRunning, localizeProblem } from '@/shared/api'
import type { ExecutionProfile, JobView } from '@/shared/api'
import { defineMessages, useMessages } from '@/shared/i18n'
import { Button } from '@/shared/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/shared/ui/card'
import { score } from '@/shared/lib/format'
import { useLanguage } from '@/shared/lib/preferences'
import { Progress } from '@/shared/ui/progress'

const messages = defineMessages({
  en: {
    title: 'CV check',
    description: (offer: boolean) =>
      offer ? 'How your CV reads against the job offer.' : 'How your CV reads to a recruiter.',
    optional: 'Optional: you can start the interview without it.',
    noCv: 'There is no CV in the documents, so there is nothing to check.',
    run: 'Check the CV',
    again: 'Check again',
    running: 'Checking the CV',
    score: (overall: string) => `Overall ${overall} / 100`,
    unavailable: 'Not enough evidence for an overall score',
    criteria: (assessed: number, total: number) =>
      `${String(assessed)} of ${String(total)} criteria assessable`,
    version: (version: number) => `version ${String(version)}`,
    open: 'Open the full CV report',
    newTab: '(opens in a new tab)',
  },
  it: {
    title: 'Controllo del CV',
    description: (offer: boolean) =>
      offer
        ? 'Come si legge il tuo CV rispetto all’offerta.'
        : 'Come si legge il tuo CV agli occhi di un selezionatore.',
    optional: 'Facoltativo: puoi iniziare il colloquio anche senza.',
    noCv: 'Tra i documenti non c’è un CV, quindi non c’è nulla da controllare.',
    run: 'Controlla il CV',
    again: 'Controlla di nuovo',
    running: 'Controllo del CV in corso',
    score: (overall: string) => `Complessivo ${overall} / 100`,
    unavailable: 'Evidenze insufficienti per un voto complessivo',
    criteria: (assessed: number, total: number) =>
      `${String(assessed)} criteri valutabili su ${String(total)}`,
    version: (version: number) => `versione ${String(version)}`,
    open: 'Apri il report completo del CV',
    newTab: '(si apre in una nuova scheda)',
  },
})

/**
 * Review the CV of an approved context, against its job offer when there is one. Each run keeps
 * the earlier versions; with `summary` the latest is summarised here and opens in full in a new
 * tab, so a preparation in progress stays where it is. A page that shows the report itself
 * leaves `summary` off. A new version belongs to `profileId`; when it is not given, to the owner
 * of the latest one.
 */
export function CvCheck({
  snapshotId,
  language,
  execution,
  profileId,
  inInterview = false,
  summary = true,
  onBusyChange,
}: {
  snapshotId: string
  language: 'it' | 'en'
  execution: ExecutionProfile
  profileId?: string | null
  /** Shown while preparing an interview, where the check is optional. */
  inInterview?: boolean
  /** Shows the latest score with a link to the full report. */
  summary?: boolean
  onBusyChange?: (busy: boolean) => void
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
      if (previous?.some(isRunning) && !list.some(isRunning)) {
        void client.invalidateQueries({ queryKey: reportsKey })
        void client.invalidateQueries({ queryKey: ['history'] })
        void client.invalidateQueries({ queryKey: ['progress'] })
      }
      return list
    },
    refetchInterval: (query) => (query.state.data?.some(isRunning) ? 1500 : false),
  })
  const reports = useQuery({ queryKey: reportsKey, queryFn: () => api.cvReviews(snapshotId) })
  const job = jobs.data?.filter((j) => j.kind === 'review_cv').at(-1)
  const running = isRunning(job)
  const owner = profileId === undefined ? (reports.data?.at(-1)?.profile_id ?? null) : profileId
  const start = useMutation({
    mutationFn: () => api.reviewCv(snapshotId, language, execution, owner),
    onSuccess: (created) => {
      rememberReportJob(created.id)
      client.setQueryData<JobView[]>(jobsKey, (old) => [...(old ?? []), created])
      void client.invalidateQueries({ queryKey: jobsKey })
    },
  })
  useEffect(() => {
    onBusyChange?.(running || start.isPending)
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
        <CardDescription>
          {t.description(hasOffer)}
          {inInterview && ` ${t.optional}`}
        </CardDescription>
      </CardHeader>
      <CardContent className="flex flex-col gap-4">
        {snapshot.data && !hasCv && <p className="text-muted-foreground">{t.noCv}</p>}
        {summary && latest && (
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
              target="_blank"
              rel="noreferrer"
              className="mt-1 inline-flex items-center gap-1 self-start text-sm text-brand-text underline"
            >
              {t.open}
              <ExternalLinkIcon className="size-3.5" aria-hidden="true" />
              <span className="sr-only">{t.newTab}</span>
            </Link>
          </div>
        )}
        {running && job && (
          <div aria-live="polite" className="flex flex-col gap-2">
            <p className="flex items-center gap-2 text-sm">
              <Loader2Icon className="size-4 animate-spin" aria-hidden="true" />
              {t.running}
              {job.message ? `: ${localizeProblem(job.message, ui)}` : ''}
            </p>
            <Progress value={job.progress * 100} />
          </div>
        )}
        {job?.status === 'failed' && job.error && (
          <p role="alert" className="text-sm text-destructive">
            {localizeProblem(job.error, ui)}
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
      </CardContent>
    </Card>
  )
}
