import { Link, useParams } from '@tanstack/react-router'
import { MicIcon, PhoneOffIcon, SquareIcon } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'

import { PROBLEM_TEXT, useAudio } from '@/audio/audio-state'
import { LevelMeter } from '@/components/level-meter'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Progress } from '@/components/ui/progress'
import { PHASE_TEXT, STEP_TEXT, formatClock, remainingSeconds } from '@/interview/state'
import type { InterviewState } from '@/interview/state'
import { useInterview } from '@/interview/use-interview'

function useNow(intervalMs: number): number {
  const [now, setNow] = useState(() => performance.now())
  useEffect(() => {
    const id = setInterval(() => {
      setNow(performance.now())
    }, intervalMs)
    return () => {
      clearInterval(id)
    }
  }, [intervalMs])
  return now
}

function Preparation({ state, onRetry }: { state: InterviewState; onRetry: () => void }) {
  const preparing = state.preparing
  const failed = preparing?.steps.some((s) => s.state === 'failed') ?? false
  return (
    <Card className="mx-auto mt-12 w-full max-w-lg">
      <CardHeader>
        <CardTitle>
          {failed ? 'The interview could not start' : 'Getting the interview ready…'}
        </CardTitle>
      </CardHeader>
      <CardContent className="flex flex-col gap-4">
        <Progress value={(preparing?.progress ?? 0) * 100} data-testid="preparation-progress" />
        <ul className="flex flex-col gap-2 text-sm">
          {preparing?.steps.map((step) => (
            <li key={step.name} className="flex items-center justify-between gap-4">
              <span>{STEP_TEXT[step.name]}</span>
              <Badge
                variant={
                  step.state === 'failed'
                    ? 'destructive'
                    : step.state === 'ready'
                      ? 'secondary'
                      : 'outline'
                }
              >
                {step.state === 'loading' ? 'loading…' : step.state}
              </Badge>
            </li>
          ))}
        </ul>
        {preparing?.steps
          .filter((s) => s.detail)
          .map((s) => (
            <div key={s.name} className="text-sm text-destructive">
              {s.detail}
            </div>
          ))}
        {failed && <Button onClick={onRetry}>Try again</Button>}
      </CardContent>
    </Card>
  )
}

function Transcript({ state }: { state: InterviewState }) {
  const bottom = useRef<HTMLDivElement>(null)
  useEffect(() => {
    bottom.current?.scrollIntoView({ block: 'end' })
  }, [state.entries])
  return (
    <Card className="min-h-0">
      <CardHeader>
        <CardTitle>Transcript</CardTitle>
      </CardHeader>
      <CardContent
        className="flex max-h-[60vh] flex-col gap-3 overflow-y-auto"
        data-testid="transcript"
      >
        {state.entries.map((entry) => (
          <div
            key={`${entry.speaker}-${entry.turnSeq}`}
            className={entry.speaker === 'interviewer' ? 'self-start' : 'self-end text-right'}
          >
            <div className="text-xs text-muted-foreground">
              {entry.speaker === 'interviewer' ? 'Interviewer' : 'You'}
              {entry.incomplete && ' · partly not transcribed'}
            </div>
            <div className={entry.final ? '' : 'text-muted-foreground italic'}>
              {entry.text || '…'}
            </div>
          </div>
        ))}
        <div ref={bottom} />
      </CardContent>
    </Card>
  )
}

/** The meeting: interviewer state, transcript, answer controls and the timer. */
export function InterviewPage() {
  const { sessionId } = useParams({ from: '/interview/$sessionId' })
  const audio = useAudio()
  const { state, answer, endAnswer, endCall, resume, retryStart } = useInterview(
    sessionId,
    audio.kit,
  )
  const now = useNow(500)

  if (!audio.kit) {
    return (
      <Card className="mx-auto mt-12 w-full max-w-lg">
        <CardHeader>
          <CardTitle>Enable the microphone to join</CardTitle>
        </CardHeader>
        <CardContent className="flex flex-col gap-4">
          <Button onClick={() => void audio.enable()} disabled={audio.enabling}>
            <MicIcon data-icon="inline-start" />
            Enable microphone and audio
          </Button>
          {audio.problem && (
            <div className="text-sm text-destructive">{PROBLEM_TEXT[audio.problem]}</div>
          )}
        </CardContent>
      </Card>
    )
  }

  if (state.ended) {
    return (
      <Card className="mx-auto mt-12 w-full max-w-lg">
        <CardHeader>
          <CardTitle>The interview has ended</CardTitle>
        </CardHeader>
        <CardContent className="flex flex-col gap-4 text-sm">
          <div>{state.ended.failure ?? `Reason: ${state.ended.reason ?? 'unknown'}`}</div>
          <Link to="/" className="underline">
            New interview
          </Link>
        </CardContent>
      </Card>
    )
  }

  if (state.status === null || state.status === 'ready') {
    return <Preparation state={state} onRetry={retryStart} />
  }

  const remaining = remainingSeconds(state, now)
  const phase = state.phase
  const answering = phase === 'candidate_speaking'
  const lastLatency = state.latenciesMs.at(-1)

  return (
    <div className="mx-auto grid max-w-5xl gap-6 p-6 md:grid-cols-[2fr_1fr]">
      <Transcript state={state} />
      <div className="flex flex-col gap-6">
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center justify-between gap-2">
              <span data-testid="timer">{remaining === null ? '–' : formatClock(remaining)}</span>
              <Badge variant="outline" data-testid="status">
                {state.status === 'paused'
                  ? 'paused'
                  : state.connection === 'closed'
                    ? 'disconnected'
                    : 'live'}
              </Badge>
            </CardTitle>
          </CardHeader>
          <CardContent className="flex flex-col gap-4">
            <div className="text-sm font-medium" data-testid="phase">
              {state.status === 'paused'
                ? 'The interview is paused'
                : phase
                  ? PHASE_TEXT[phase]
                  : ''}
            </div>
            {answering && <LevelMeter dbfs={audio.level} />}
            {state.status === 'paused' ? (
              <Button onClick={resume}>Resume</Button>
            ) : answering ? (
              <Button onClick={endAnswer} variant="secondary">
                <SquareIcon data-icon="inline-start" />
                End of answer
              </Button>
            ) : (
              <Button onClick={answer} disabled={phase !== 'awaiting_candidate'}>
                <MicIcon data-icon="inline-start" />
                Answer
              </Button>
            )}
            <Button variant="destructive" onClick={endCall}>
              <PhoneOffIcon data-icon="inline-start" />
              End call
            </Button>
          </CardContent>
        </Card>
        {state.notice && (
          <Alert>
            <AlertTitle>Note</AlertTitle>
            <AlertDescription>{state.notice}</AlertDescription>
          </Alert>
        )}
        {state.connection === 'closed' && (
          <Alert variant="destructive">
            <AlertTitle>Connection lost</AlertTitle>
            <AlertDescription>
              Reload the page to rejoin; the interview is paused meanwhile.
            </AlertDescription>
          </Alert>
        )}
        {lastLatency !== undefined && (
          <div className="text-xs text-muted-foreground" data-testid="latency">
            Reply started {(lastLatency / 1000).toFixed(2)} s after the end of your answer (last of{' '}
            {state.latenciesMs.length}).
          </div>
        )}
      </div>
    </div>
  )
}
