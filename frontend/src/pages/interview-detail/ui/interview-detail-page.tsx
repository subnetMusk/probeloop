import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useInstallation } from '@/features/installation'
import { Link, useNavigate, useParams, useSearch } from '@tanstack/react-router'
import { ArrowDownIcon, CheckCircle2Icon, TriangleAlertIcon, XIcon } from 'lucide-react'
import { useRef, useState } from 'react'

import {
  conversationOf,
  interviewHistoryQuery,
  interviewLabels,
  labelOf,
} from '@/entities/interview'
import { rememberReportJob } from '@/entities/report-job'
import { api, isRunning, localizeProblem, sessionFile } from '@/shared/api'
import type { JobView, SessionView } from '@/shared/api'
import { useMessages } from '@/shared/i18n'
import { clock, minutes, shortDate } from '@/shared/lib/format'
import { usePaged } from '@/shared/lib/pagination'
import { useLanguage } from '@/shared/lib/preferences'
import { Badge } from '@/shared/ui/badge'
import { Button } from '@/shared/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/shared/ui/card'
import { ConfirmDialog } from '@/shared/ui/confirm-dialog'
import { Page } from '@/shared/ui/page-header'
import { Pager } from '@/shared/ui/pager'
import { Progress } from '@/shared/ui/progress'
import { nextFlagged, transcriptReview } from '../model/review'
import { Answer } from './answer'
import { InterviewerTurn } from './interviewer-turn'
import { transcriptMessages } from './messages'
import { TurnAudioProvider } from './turn-audio'
import { useTurnAudio } from './turn-audio-context'

/**
 * The transcript review: the conversation as chat bubbles, each with its audio and an in-place
 * editor, beside the recording, the answers to check, the second transcription and the report.
 * It fills the window below the header (`chrome: 'workspace'`); each column scrolls on its own.
 */
export function InterviewDetailPage() {
  const { sessionId } = useParams({ from: '/interviews/$sessionId/' })
  const t = useMessages(transcriptMessages)
  const session = useQuery({
    queryKey: ['session', sessionId],
    queryFn: () => api.session(sessionId),
  })
  const data = session.data
  if (!data)
    return (
      <Page>
        <p role={session.error ? 'alert' : 'status'}>{session.error?.message ?? t.loading}</p>
      </Page>
    )
  return (
    <TurnAudioProvider>
      <Review data={data} />
    </TurnAudioProvider>
  )
}

function Review({ data }: { data: SessionView }) {
  const installation = useInstallation()
  const sessionId = data.id
  const search = useSearch({ from: '/interviews/$sessionId/' })
  const navigate = useNavigate()
  const t = useMessages(transcriptMessages)
  const labels = useMessages(interviewLabels)
  const language = useLanguage()
  const client = useQueryClient()
  const player = useTurnAudio()
  const [confirming, setConfirming] = useState(false)
  const visited = useRef<number | null>(null)
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
      setConfirming(false)
      rememberReportJob(job.id)
      client.setQueryData<JobView[]>(['jobs', sessionId], (old) => [...(old ?? []), job])
      void client.invalidateQueries({ queryKey: ['jobs', sessionId] })
    },
  })
  const ended = data.status === 'ended' || data.status === 'failed'
  const voice = data.modality === 'voice'
  const hasAudio = data.turns.some((turn) => turn.audio)
  const meta = history.data?.find((item) => item.id === data.id)
  const latest = reports.data?.at(-1)
  const busy = isRunning(refineJob) || isRunning(reportJob)
  const check = transcriptReview(data)
  const answers = data.turns.filter((turn) => turn.speaker === 'candidate').length
  const spoken = meta?.effective_s ?? Math.max(0, ...data.turns.map((turn) => turn.elapsed_s))
  const goTo = (seq: number) => {
    visited.current = seq
    const target = document.getElementById(`turn-${String(seq)}`)
    target?.scrollIntoView({ block: 'center', behavior: 'smooth' })
    target?.focus({ preventScroll: true })
  }
  return (
    <main className="flex flex-1 flex-col gap-3 px-4 pt-2 pb-3 lg:min-h-0 lg:px-6">
      {/* One compact row, so the conversation keeps most of the window's height. */}
      <header className="flex flex-col gap-2 sm:flex-row sm:flex-wrap sm:items-center sm:justify-between">
        <div className="flex min-w-0 flex-wrap items-center gap-x-4 gap-y-1">
          <h1 className="font-heading text-2xl font-bold tracking-tight">{t.title}</h1>
          <p className="text-sm text-muted-foreground">
            {[
              labelOf(labels, 'types', data.interview_type),
              shortDate(data.created_at, language),
              meta?.effective_s != null && minutes(meta.effective_s),
            ]
              .filter(Boolean)
              .join(' · ')}
          </p>
          <div className="flex flex-wrap gap-2">
            <Badge variant="secondary">{labelOf(labels, 'statuses', data.status)}</Badge>
            {data.execution_profile && (
              <Badge variant="outline">
                {labelOf(labels, 'execution', data.execution_profile)}
              </Badge>
            )}
          </div>
        </div>
        <div className="flex shrink-0 flex-wrap items-center gap-2">
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
          {!ended && (
            <Button asChild>
              <Link to="/live-interview/$sessionId" params={{ sessionId }}>
                {t.resume}
              </Link>
            </Button>
          )}
        </div>
      </header>
      {search.ended && (
        <div
          role="status"
          className="flex flex-wrap items-center gap-x-4 gap-y-2 rounded-xl border border-success/30 bg-success/10 px-4 py-2 text-sm"
        >
          <CheckCircle2Icon className="size-5 shrink-0 text-success" aria-hidden />
          <p className="min-w-0 flex-1">
            <span className="font-semibold">{t.endedTitle}</span>{' '}
            <span data-testid="ended-summary">{t.endedSummary(answers, clock(spoken))}</span>
            {voice && <span className="text-muted-foreground"> · {t.endedNext}</span>}
          </p>
          <Button asChild size="sm" variant="outline">
            <Link to="/new-interview">{t.newInterview}</Link>
          </Button>
          <Button
            size="icon-sm"
            variant="ghost"
            aria-label={t.dismiss}
            onClick={() => {
              void navigate({
                to: '/interviews/$sessionId',
                params: { sessionId },
                search: {},
                replace: true,
              })
            }}
          >
            <XIcon />
          </Button>
        </div>
      )}
      <div className="grid flex-1 items-start gap-4 lg:min-h-0 lg:grid-cols-[minmax(0,1fr)_22rem] lg:items-stretch xl:grid-cols-[minmax(0,1fr)_25rem]">
        <section
          aria-label={t.conversation}
          data-testid="conversation"
          className="rounded-2xl border bg-card lg:min-h-0 lg:overflow-y-auto"
        >
          <div className="flex flex-col gap-6 p-4 sm:p-6">
            {data.turns.length === 0 && <p>{t.noTurns}</p>}
            {conversationOf(data.turns).map((block) => (
              <section
                key={block.number}
                aria-labelledby={`question-${String(block.number)}`}
                className="flex flex-col gap-3"
              >
                <h2
                  id={`question-${String(block.number)}`}
                  className="flex items-center gap-3 text-xs font-semibold tracking-wide text-brand-text uppercase"
                >
                  <span aria-hidden="true" className="h-px flex-1 bg-border" />
                  {t.question(block.number)}
                  <span aria-hidden="true" className="h-px flex-1 bg-border" />
                </h2>
                {block.questions.map((turn) => (
                  <InterviewerTurn key={turn.seq} turn={turn} question={block.number} />
                ))}
                {block.answers.map(({ turn, number }) => (
                  <Answer key={turn.seq} session={data} turn={turn} number={number} />
                ))}
              </section>
            ))}
          </div>
        </section>
        <aside className="flex flex-col gap-4 lg:min-h-0 lg:overflow-y-auto [&>*]:shrink-0">
          {ended && voice && (
            <Card
              data-testid="transcript-review"
              className={check.flagged.length > 0 ? 'border-warning/40' : undefined}
            >
              <CardHeader>
                <CardTitle role="heading" aria-level={2} className="flex items-center gap-2">
                  {check.flagged.length > 0 ? (
                    <TriangleAlertIcon className="size-4 text-warning" aria-hidden />
                  ) : (
                    <CheckCircle2Icon className="size-4 text-success" aria-hidden />
                  )}
                  {t.reviewTitle}
                </CardTitle>
              </CardHeader>
              <CardContent className="flex flex-col gap-3 text-sm">
                {check.flagged.length > 0 ? (
                  <>
                    <p className="text-muted-foreground">{t.reviewNote}</p>
                    <ul className="flex flex-wrap gap-2">
                      {check.flagged.map((item) => (
                        <li key={item.seq}>
                          <a
                            href={`#turn-${String(item.seq)}`}
                            className="text-brand-text underline underline-offset-4"
                            onClick={(event) => {
                              event.preventDefault()
                              goTo(item.seq)
                            }}
                          >
                            {t.reviewItem(item.number)}
                          </a>
                        </li>
                      ))}
                    </ul>
                    <Button
                      variant="outline"
                      size="sm"
                      className="self-start"
                      onClick={() => {
                        const next = nextFlagged(check.flagged, visited.current)
                        if (next) goTo(next.seq)
                      }}
                    >
                      <ArrowDownIcon data-icon="inline-start" />
                      {t.nextFlagged}
                    </Button>
                  </>
                ) : (
                  <p className="text-muted-foreground">{t.reviewClear}</p>
                )}
                <p className="text-muted-foreground">{t.refineNote}</p>
              </CardContent>
            </Card>
          )}
          {ended && (
            <Card>
              <CardHeader>
                <CardTitle role="heading" aria-level={2}>
                  {hasAudio ? t.recording : t.exports}
                </CardTitle>
              </CardHeader>
              <CardContent className="flex flex-col gap-3 text-sm">
                {hasAudio && (
                  <audio
                    controls
                    preload="none"
                    aria-label={t.recording}
                    src={sessionFile(sessionId, 'audio/interview.wav')}
                    className="w-full"
                    onPlay={() => {
                      player?.stop()
                    }}
                  />
                )}
                <ul className="flex flex-wrap gap-x-4 gap-y-1">
                  {[
                    ...(hasAudio ? ['audio/interview.wav'] : []),
                    'transcript.md',
                    'transcript.json',
                  ].map((name) => (
                    <li key={name}>
                      <a
                        href={sessionFile(sessionId, name)}
                        download
                        className="text-brand-text underline underline-offset-4"
                      >
                        {name.replace('audio/', '')}
                      </a>
                    </li>
                  ))}
                </ul>
              </CardContent>
            </Card>
          )}
          {ended && voice && installation.data?.config.refinement !== false && (
            <Card>
              <CardHeader>
                <CardTitle role="heading" aria-level={2}>
                  {t.refine}
                </CardTitle>
              </CardHeader>
              <CardContent className="flex flex-col gap-3 text-sm">
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
                    // A spoken transcript is confirmed first while it may still hold errors.
                    if (check.flagged.length > 0 || check.liveOnly > 0) setConfirming(true)
                    else review.mutate()
                  }}
                >
                  {t.generate}
                </Button>
                <ConfirmDialog
                  open={confirming}
                  tone="default"
                  title={t.confirmTitle}
                  description={
                    <span className="flex flex-col gap-2">
                      {check.flagged.length > 0 && (
                        <span>{t.confirmFlagged(check.flagged.length)}</span>
                      )}
                      {check.liveOnly > 0 && <span>{t.confirmLive(check.liveOnly)}</span>}
                      <span>{t.confirmNote}</span>
                    </span>
                  }
                  confirm={t.confirmGo}
                  cancel={t.confirmBack}
                  pending={review.isPending}
                  error={review.error?.message}
                  onConfirm={() => {
                    review.mutate()
                  }}
                  onCancel={() => {
                    setConfirming(false)
                  }}
                />
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
                        {report.overall ?? '—'} / 100
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
          <Button asChild variant="outline" className="self-start">
            <Link to="/interviews">{t.all}</Link>
          </Button>
        </aside>
      </div>
    </main>
  )
}
