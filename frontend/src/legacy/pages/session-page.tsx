import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Link, useParams } from '@tanstack/react-router'
import {
  ArrowLeftIcon,
  DownloadIcon,
  HistoryIcon,
  Loader2Icon,
  PencilIcon,
  RefreshCwIcon,
} from 'lucide-react'
import { useState } from 'react'

import { api, isRunning, sessionFile } from '@/shared/api'
import type { JobView, SessionView, TurnView, WordView } from '@/shared/api'
import { Alert, AlertDescription, AlertTitle } from '@/shared/ui/alert'
import { Badge } from '@/shared/ui/badge'
import { Button } from '@/shared/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/shared/ui/card'
import { Progress } from '@/shared/ui/progress'
import { Textarea } from '@/shared/ui/textarea'
import { INTERVIEW_TYPES, STATUS_LABELS, clock, dateTime } from '@/shared/lib/format'
import { InterviewReportPanel } from '@/legacy/reports/interview-report-panel'
import { T } from '@/shared/i18n'
import { localise } from '@/shared/i18n'

/** Words the recogniser was unsure about are highlighted for review. */
export const DOUBTFUL_BELOW = 0.5

const SOURCE_LABELS: Record<string, string> = {
  stt: 'live transcript',
  retranscription: 'refined',
  user_edit: 'edited',
}

function Words({ words }: { words: WordView[] }) {
  return (
    <>
      {words.map((word, index) => {
        const doubtful = word.probability !== null && word.probability < DOUBTFUL_BELOW
        return (
          <span key={index}>
            {index > 0 && ' '}
            {doubtful ? (
              <mark
                className="rounded-sm bg-amber-100 px-0.5 text-inherit underline decoration-amber-500 decoration-dotted dark:bg-amber-500/20"
                title={`Recognised with ${String(Math.round((word.probability ?? 0) * 100))}% confidence`}
                data-testid="doubtful-word"
              >
                {word.text}
              </mark>
            ) : (
              word.text
            )}
          </span>
        )
      })}
    </>
  )
}

function Answer({ session, turn }: { session: SessionView; turn: TurnView }) {
  const queryClient = useQueryClient()
  const [draft, setDraft] = useState<string | null>(null)
  const [history, setHistory] = useState(false)
  const save = useMutation({
    mutationFn: (text: string) => api.editAnswer(session.id, turn.seq, text),
    onSuccess: (updated) => {
      queryClient.setQueryData(['session', session.id], updated)
      setDraft(null)
    },
  })
  const current = turn.revisions.at(-1)
  const editable = session.status === 'ended' || session.status === 'failed'

  return (
    <div className="flex flex-col gap-2">
      {draft === null ? (
        <p className="leading-relaxed" data-testid="answer-text">
          {turn.words.length > 0 ? (
            <Words words={turn.words} />
          ) : (
            turn.text || (
              <em>
                <T text={'(no speech)'} />
              </em>
            )
          )}
        </p>
      ) : (
        <div className="flex flex-col gap-2">
          <Textarea
            value={draft}
            onChange={(event) => {
              setDraft(event.target.value)
            }}
            aria-label={localise('Corrected answer')}
            autoFocus
          />
          <div className="flex gap-2">
            <Button
              size="sm"
              disabled={save.isPending || draft.trim() === turn.text}
              onClick={() => {
                save.mutate(draft)
              }}
            >
              <T text={save.isPending ? 'Saving…' : 'Save correction'} />
            </Button>
            <Button
              size="sm"
              variant="ghost"
              onClick={() => {
                setDraft(null)
              }}
            >
              <T text={'Cancel'} />
            </Button>
          </div>
          {save.error && <p className="text-sm text-destructive">{save.error.message}</p>}
        </div>
      )}
      <div className="flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
        {current && (
          <Badge variant="outline" title={current.engine_ref ?? undefined}>
            <T text={SOURCE_LABELS[current.source] ?? current.source} />
          </Badge>
        )}
        {editable && draft === null && (
          <Button
            size="xs"
            variant="ghost"
            onClick={() => {
              setDraft(turn.text)
            }}
          >
            <PencilIcon data-icon="inline-start" />
            <T text={'Correct'} />
          </Button>
        )}
        {turn.revisions.length > 1 && (
          <Button
            size="xs"
            variant="ghost"
            onClick={() => {
              setHistory(!history)
            }}
          >
            <HistoryIcon data-icon="inline-start" />
            <T text={history ? 'Hide' : 'Show'} /> {turn.revisions.length - 1}
            <T text={'earlier version'} />
            {turn.revisions.length > 2 ? 's' : ''}
          </Button>
        )}
      </div>
      {history && (
        <ol className="flex flex-col gap-1 border-l-2 pl-3 text-sm text-muted-foreground">
          {turn.revisions
            .slice(0, -1)
            .reverse()
            .map((revision) => (
              <li key={revision.number}>
                <span className="text-xs font-medium">
                  {String(revision.number)}.{' '}
                  <T text={SOURCE_LABELS[revision.source] ?? revision.source} />:
                </span>{' '}
                {revision.text}
              </li>
            ))}
        </ol>
      )}
    </div>
  )
}

function Turn({ session, turn }: { session: SessionView; turn: TurnView }) {
  const interviewer = turn.speaker === 'interviewer'
  return (
    <li
      id={`turn-${turn.seq}`}
      className="scroll-mt-8 grid gap-2 py-4 sm:grid-cols-[8rem_1fr]"
      data-testid={`turn-${turn.speaker}`}
    >
      <div className="flex flex-col gap-1 text-sm">
        <span className={interviewer ? 'font-medium text-indigo-600' : 'font-medium'}>
          <T text={interviewer ? 'Interviewer' : 'You'} />
        </span>
        <span className="text-xs text-muted-foreground">{clock(turn.elapsed_s)}</span>
      </div>
      <div className="flex flex-col gap-2">
        {interviewer ? (
          <p className="leading-relaxed text-muted-foreground">
            {turn.text}
            {turn.status === 'interrupted' && (
              <em>
                <T text={' (interrupted)'} />
              </em>
            )}
          </p>
        ) : (
          <Answer session={session} turn={turn} />
        )}
        {turn.audio && (
          <audio controls preload="none" src={turn.audio} className="h-8 w-full max-w-sm" />
        )}
      </div>
    </li>
  )
}

function Refinement({ session, job }: { session: SessionView; job: JobView | undefined }) {
  const queryClient = useQueryClient()
  const start = useMutation({
    mutationFn: () => api.refine(session.id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['jobs', session.id] }),
  })
  if (session.modality !== 'voice') return null
  const running = isRunning(job)
  return (
    <Card>
      <CardHeader>
        <CardTitle>
          <T text={'Accurate transcript'} />
        </CardTitle>
        <CardDescription>
          <T
            text={
              'After the call your answers are transcribed again with a slower, more accurate recogniser. Words it was unsure about are highlighted: correct them before generating a report.'
            }
          />
        </CardDescription>
      </CardHeader>
      <CardContent className="flex flex-col gap-3">
        {running && job && (
          <div className="flex flex-col gap-2" data-testid="refine-progress">
            <div className="flex items-center gap-2 text-sm">
              <Loader2Icon className="size-4 animate-spin" />
              {job.status === 'queued'
                ? 'Waiting to start…'
                : `Transcribing your answers… ${job.message ?? ''}`}
            </div>
            <Progress value={job.progress * 100} />
          </div>
        )}
        {job?.status === 'succeeded' && (
          <p className="text-sm text-muted-foreground" data-testid="refine-done">
            <T text={'Done:'} />
            {typeof job.result?.revised === 'number' ? String(job.result.revised) : '0'}{' '}
            <T text={'answers transcribed again.'} />
          </p>
        )}
        {job?.status === 'failed' && (
          <Alert variant="destructive">
            <AlertTitle>
              <T text={'The transcript could not be refined'} />
            </AlertTitle>
            <AlertDescription>{job.error && <T text={job.error} />}</AlertDescription>
          </Alert>
        )}
        {!running && (
          <Button
            variant="outline"
            className="self-start"
            disabled={start.isPending}
            onClick={() => {
              start.mutate()
            }}
          >
            <RefreshCwIcon data-icon="inline-start" />
            {job ? 'Transcribe again' : 'Transcribe accurately'}
          </Button>
        )}
        {start.error && <p className="text-sm text-destructive">{start.error.message}</p>}
      </CardContent>
    </Card>
  )
}

/** A past interview: its recording, the transcript to review and correct, the downloads. */
export function SessionPage() {
  const { sessionId } = useParams({ from: '/sessions/$sessionId' })
  const queryClient = useQueryClient()
  const session = useQuery({
    queryKey: ['session', sessionId],
    queryFn: () => api.session(sessionId),
  })
  const jobs = useQuery({
    queryKey: ['jobs', sessionId],
    queryFn: async () => {
      const list = await api.sessionJobs(sessionId)
      const previous = queryClient.getQueryData<JobView[]>(['jobs', sessionId])
      // A job that just finished changed the transcript.
      if (previous?.some(isRunning) && !list.some(isRunning)) {
        void queryClient.invalidateQueries({ queryKey: ['session', sessionId] })
      }
      return list
    },
    refetchInterval: (query) => (query.state.data?.some(isRunning) ? 1500 : false),
  })
  const refineJob = jobs.data?.filter((j) => j.kind === 'refine_transcript').at(-1)

  if (session.error) {
    return (
      <div className="mx-auto max-w-3xl px-6 py-10">
        <Alert variant="destructive">
          <AlertTitle>
            <T text={'The interview could not be loaded'} />
          </AlertTitle>
          <AlertDescription>{session.error.message}</AlertDescription>
        </Alert>
      </div>
    )
  }
  const data = session.data
  if (!data) return null
  const ended = data.status === 'ended' || data.status === 'failed'
  const hasAudio = data.turns.some((t) => t.audio)

  return (
    <div className="mx-auto flex max-w-4xl flex-col gap-6 px-6 py-10">
      <Button asChild variant="ghost" className="self-start">
        <Link to="/sessions">
          <ArrowLeftIcon data-icon="inline-start" />
          <T text={'All interviews'} />
        </Link>
      </Button>
      <div className="flex flex-col gap-2">
        <div className="flex flex-wrap items-center gap-2">
          <h1 className="font-heading text-3xl font-semibold tracking-tight">
            <T text={INTERVIEW_TYPES[data.interview_type] ?? data.interview_type} />
            <T text={'interview'} />
          </h1>
          <Badge variant="secondary">
            <T text={STATUS_LABELS[data.status] ?? data.status} />
          </Badge>
        </div>
        <p className="text-muted-foreground">
          {dateTime(data.created_at)} · {data.language.toUpperCase()} · {data.difficulty}
        </p>
      </div>

      {ended && hasAudio && (
        <Card>
          <CardHeader>
            <CardTitle>
              <T text={'Recording'} />
            </CardTitle>
            <CardDescription>
              <T text={'The whole conversation, both voices.'} />
            </CardDescription>
          </CardHeader>
          <CardContent className="flex flex-col gap-3">
            <audio
              controls
              preload="none"
              src={sessionFile(data.id, 'audio/interview.wav')}
              className="w-full"
            />
          </CardContent>
        </Card>
      )}

      {ended && <Refinement session={data} job={refineJob} />}
      {ended && data.turns.some((t) => t.speaker === 'candidate') && (
        <InterviewReportPanel sessionId={data.id} jobs={jobs.data ?? []} />
      )}

      <Card>
        <CardHeader className="flex flex-row flex-wrap items-start justify-between gap-2">
          <div className="flex flex-col gap-1.5">
            <CardTitle>
              <T text={'Transcript'} />
            </CardTitle>
            <CardDescription>
              {ended
                ? 'Correct any answer that was recognised wrongly: corrections are kept as new versions.'
                : 'The interview is not over yet.'}
            </CardDescription>
          </div>
          {ended && (
            <div className="flex flex-wrap gap-2">
              {['transcript.md', 'transcript.json'].map((name) => (
                <Button key={name} asChild size="sm" variant="outline">
                  <a href={sessionFile(data.id, name)} download>
                    <DownloadIcon data-icon="inline-start" />
                    {name}
                  </a>
                </Button>
              ))}
              {hasAudio && (
                <Button asChild size="sm" variant="outline">
                  <a href={sessionFile(data.id, 'audio/interview.wav')} download>
                    <DownloadIcon data-icon="inline-start" />
                    interview.wav
                  </a>
                </Button>
              )}
            </div>
          )}
        </CardHeader>
        <CardContent>
          <ol className="divide-y">
            {data.turns.map((turn) => (
              <Turn key={turn.seq} session={data} turn={turn} />
            ))}
          </ol>
        </CardContent>
      </Card>
    </div>
  )
}
