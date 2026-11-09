import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Link, useParams } from '@tanstack/react-router'

import {
  conversationOf,
  interviewHistoryQuery,
  interviewLabels,
  labelOf,
} from '@/entities/interview'
import { rememberReportJob } from '@/entities/report-job'
import { api, isRunning, localizeProblem, sessionFile } from '@/shared/api'
import type { JobView } from '@/shared/api'
import { useMessages } from '@/shared/i18n'
import { clock, minutes, shortDate } from '@/shared/lib/format'
import { usePaged } from '@/shared/lib/pagination'
import { useLanguage } from '@/shared/lib/preferences'
import { Badge } from '@/shared/ui/badge'
import { Button } from '@/shared/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/shared/ui/card'
import { Page, PageHeader } from '@/shared/ui/page-header'
import { Pager } from '@/shared/ui/pager'
import { Progress } from '@/shared/ui/progress'
import { Answer } from './answer'
import { transcriptMessages } from './messages'

export function InterviewDetailPage() {
  const { sessionId } = useParams({ from: '/interviews/$sessionId/' })
  const t = useMessages(transcriptMessages)
  const labels = useMessages(interviewLabels)
  const language = useLanguage()
  const client = useQueryClient()
  const session = useQuery({
    queryKey: ['session', sessionId],
    queryFn: () => api.session(sessionId),
  })
  const history = useQuery(interviewHistoryQuery)
  const jobs = useQuery({
    queryKey: ['jobs', sessionId],
    queryFn: async () => {
      const list = await api.sessionJobs(sessionId)
      const previous = client.getQueryData<JobView[]>(['jobs', sessionId])
      if (previous?.some(isRunning) && !list.some(isRunning)) {
        await Promise.all([
          client.invalidateQueries({ queryKey: ['session', sessionId] }),
          client.invalidateQueries({ queryKey: ['interview-reports', sessionId] }),
        ])
      }
      return list
    },
    refetchInterval: (query) => (query.state.data?.some(isRunning) ? 1500 : false),
  })
  const reports = useQuery({
    queryKey: ['interview-reports', sessionId],
    queryFn: () => api.interviewReports(sessionId),
  })
  const versions = usePaged(reports.data?.toReversed() ?? [], 4)
  const refineJob = jobs.data?.filter((job) => job.kind === 'refine_transcript').at(-1)
  const reportJob = jobs.data?.filter((job) => job.kind === 'review_interview').at(-1)
  const refine = useMutation({
    mutationFn: () => api.refine(sessionId),
    onSuccess: (job) => {
      client.setQueryData<JobView[]>(['jobs', sessionId], (old) => [...(old ?? []), job])
      void client.invalidateQueries({ queryKey: ['jobs', sessionId] })
    },
  })
  const review = useMutation({
    mutationFn: () => api.reviewInterview(sessionId, language),
    onSuccess: (job) => {
      rememberReportJob(job.id)
      client.setQueryData<JobView[]>(['jobs', sessionId], (old) => [...(old ?? []), job])
      void client.invalidateQueries({ queryKey: ['jobs', sessionId] })
    },
  })
  const data = session.data
  if (!data)
    return (
      <Page>
        <p role={session.error ? 'alert' : 'status'}>{session.error?.message ?? t.loading}</p>
      </Page>
    )
  const ended = data.status === 'ended' || data.status === 'failed'
  const hasAudio = data.turns.some((turn) => turn.audio)
  const meta = history.data?.find((item) => item.id === data.id)
  const latest = reports.data?.at(-1)
  const busy = isRunning(refineJob) || isRunning(reportJob)
  return (
    <Page>
      <PageHeader
        title={t.title}
        description={[
          labelOf(labels, 'types', data.interview_type),
          shortDate(data.created_at, language),
          meta?.effective_s != null && minutes(meta.effective_s),
        ]
          .filter(Boolean)
          .join(' · ')}
        actions={
          <>
            {latest && (
              <Button asChild size="sm">
                <Link
                  to="/interviews/$sessionId/reports/$reportId"
                  params={{ sessionId, reportId: latest.id }}
                >
                  {t.latest}
                </Link>
              </Button>
            )}
            {ended &&
              ['transcript.md', 'transcript.json'].map((name) => (
                <Button key={name} asChild variant="outline" size="sm">
                  <a href={sessionFile(sessionId, name)} download>
                    {name}
                  </a>
                </Button>
              ))}
            {!ended && (
              <Button asChild>
                <Link to="/live-interview/$sessionId" params={{ sessionId }}>
                  {t.resume}
                </Link>
              </Button>
            )}
          </>
        }
      >
        <div className="flex flex-wrap gap-2">
          <Badge variant="secondary">{labelOf(labels, 'statuses', data.status)}</Badge>
          {data.execution_profile && (
            <Badge variant="outline">{labelOf(labels, 'execution', data.execution_profile)}</Badge>
          )}
        </div>
      </PageHeader>
      <div className="grid items-start gap-8 lg:grid-cols-[minmax(0,1fr)_20rem]">
        <div className="flex min-w-0 flex-col gap-5">
          {data.turns.length === 0 && <p>{t.noTurns}</p>}
          {conversationOf(data.turns).map((block) => (
            <section
              key={block.number}
              aria-labelledby={`question-${String(block.number)}`}
              className="flex flex-col gap-4 rounded-2xl border bg-card p-5 sm:p-6"
            >
              <h2
                id={`question-${String(block.number)}`}
                className="text-sm font-semibold text-brand-text"
              >
                {t.question(block.number)}
              </h2>
              {block.questions.map((turn) => (
                <div id={`turn-${String(turn.seq)}`} key={turn.seq} data-testid="turn-interviewer">
                  <p className="text-lg leading-relaxed">
                    {turn.text} {turn.status === 'interrupted' && <em>{t.interrupted}</em>}
                  </p>
                  <p className="mt-1 text-xs text-muted-foreground">{clock(turn.elapsed_s)}</p>
                </div>
              ))}
              {block.answers.map(({ turn, number }) => (
                <Answer key={turn.seq} session={data} turn={turn} number={number} />
              ))}
            </section>
          ))}
        </div>
        <aside className="flex flex-col gap-5 lg:sticky lg:top-6">
          {hasAudio && ended && (
            <Card>
              <CardHeader>
                <CardTitle role="heading" aria-level={2}>
                  {t.recording}
                </CardTitle>
              </CardHeader>
              <CardContent className="flex flex-col gap-3">
                <audio
                  controls
                  preload="none"
                  aria-label={t.recording}
                  src={sessionFile(sessionId, 'audio/interview.wav')}
                  className="w-full"
                />
                <a
                  href={sessionFile(sessionId, 'audio/interview.wav')}
                  download
                  className="text-sm text-brand-text underline"
                >
                  interview.wav
                </a>
              </CardContent>
            </Card>
          )}
          {ended && data.modality === 'voice' && (
            <Card>
              <CardHeader>
                <CardTitle role="heading" aria-level={2}>
                  {t.refine}
                </CardTitle>
              </CardHeader>
              <CardContent className="flex flex-col gap-3 text-sm">
                <p className="text-muted-foreground">{t.refineNote}</p>
                {isRunning(refineJob) && (
                  <div role="status">
                    <p>{refineJob?.status === 'queued' ? t.queued : t.refining}</p>
                    <Progress value={(refineJob?.progress ?? 0) * 100} />
                  </div>
                )}
                {refineJob?.status === 'succeeded' && (
                  <p data-testid="refine-done">
                    {t.refined(
                      typeof refineJob.result?.revised === 'number' ? refineJob.result.revised : 0,
                    )}
                  </p>
                )}
                {refineJob?.error && (
                  <p role="alert" className="text-destructive">
                    {localizeProblem(refineJob.error, language)}
                  </p>
                )}
                <Button
                  variant="outline"
                  disabled={busy || refine.isPending}
                  onClick={() => {
                    refine.mutate()
                  }}
                >
                  {refineJob ? t.again : t.refineStart}
                </Button>
              </CardContent>
            </Card>
          )}
          {ended && data.turns.some((turn) => turn.speaker === 'candidate') && (
            <Card data-testid="interview-report-panel">
              <CardHeader>
                <CardTitle role="heading" aria-level={2}>
                  {t.assessment}
                </CardTitle>
              </CardHeader>
              <CardContent className="flex flex-col gap-3 text-sm">
                <p className="text-muted-foreground">{t.assessmentNote}</p>
                <Button
                  disabled={busy || review.isPending || jobs.isPending}
                  onClick={() => {
                    review.mutate()
                  }}
                >
                  {t.generate}
                </Button>
                {isRunning(refineJob) && <p role="status">{t.refinementWait}</p>}
                {isRunning(reportJob) && (
                  <div role="status">
                    <p>
                      {reportJob?.message ? localizeProblem(reportJob.message, language) : t.queued}
                    </p>
                    <Progress value={(reportJob?.progress ?? 0) * 100} />
                  </div>
                )}
                {reportJob?.error && (
                  <p role="alert" className="text-destructive">
                    {localizeProblem(reportJob.error, language)}
                  </p>
                )}
                <ul className="divide-y">
                  {versions.items.map((report) => (
                    <li key={report.id} className="py-2">
                      <Link
                        className="text-brand-text underline"
                        to="/interviews/$sessionId/reports/$reportId"
                        params={{ sessionId, reportId: report.id }}
                      >
                        {t.open(report.version)} · {report.language.toUpperCase()} ·{' '}
                        {report.overall ?? '—'} / 5
                      </Link>
                    </li>
                  ))}
                </ul>
                <Pager
                  label={t.versions}
                  page={versions.page}
                  pages={versions.pages}
                  onPage={versions.setPage}
                />
              </CardContent>
            </Card>
          )}
          {(refine.error ?? review.error ?? jobs.error ?? reports.error) && (
            <p role="alert" className="text-sm text-destructive">
              {(refine.error ?? review.error ?? jobs.error ?? reports.error)?.message}
            </p>
          )}
        </aside>
      </div>
      <Button asChild variant="outline" className="self-start">
        <Link to="/interviews">{t.all}</Link>
      </Button>
    </Page>
  )
}
