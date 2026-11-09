import { Link, useParams } from '@tanstack/react-router'
import { CheckIcon, Loader2Icon, MicIcon, PhoneOffIcon, RotateCcwIcon, XIcon } from 'lucide-react'
import type { ReactNode } from 'react'
import { useCallback, useEffect, useState } from 'react'

import { audioMessages, useAudio } from '@/shared/lib/audio'
import { Captions } from '@/widgets/meeting'
import { ControlBar } from '@/widgets/meeting'
import { Dots, ParticipantTile } from '@/widgets/meeting'
import { TranscriptPanel } from '@/widgets/meeting'
import { Button } from '@/shared/ui/button'
import { Progress } from '@/shared/ui/progress'
import { Wordmark } from '@/shared/ui/wordmark'
import { micLevel, useAnimatedLevel } from '@/shared/lib/hooks'
import { useHotkey } from '@/shared/lib/hooks'
import { formatClock, remainingSeconds } from '@/features/live-interview'
import type { Entry, InterviewState } from '@/features/live-interview'
import { useInterview } from '@/features/live-interview'
import { cn } from '@/shared/lib/utils'
import { useMessages } from '@/shared/i18n'
import { meetingMessages } from '@/widgets/meeting'
import { callMessages } from './messages'

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

/** The dark stage every screen of the call shares. */
function Stage({ children, className }: { children: ReactNode; className?: string }) {
  return (
    <div className={cn('dark flex h-svh flex-col bg-zinc-950 text-zinc-100', className)}>
      {children}
    </div>
  )
}

function Lobby({ title, children }: { title: string; children: ReactNode }) {
  return (
    <Stage className="items-center justify-center p-6">
      <div className="w-full max-w-md rounded-2xl bg-zinc-900 p-6 ring-1 ring-white/5">
        <h1 className="mb-5 font-heading text-lg font-semibold">{title}</h1>
        {children}
      </div>
    </Stage>
  )
}

function Preparation({ state, onRetry }: { state: InterviewState; onRetry: () => void }) {
  const t = useMessages(callMessages)
  const preparing = state.preparing
  const failed = preparing?.steps.some((s) => s.state === 'failed') ?? false
  return (
    <Lobby title={failed ? t.failed : t.joining}>
      <div className="flex flex-col gap-5">
        <Progress value={(preparing?.progress ?? 0) * 100} data-testid="preparation-progress" />
        <ul className="flex flex-col gap-3 text-sm">
          {preparing?.steps.map((step) => (
            <li
              key={step.name}
              className="flex items-center gap-3"
              data-testid={`step-${step.name}`}
            >
              {step.state === 'loading' && (
                <Loader2Icon className="size-4 animate-spin text-zinc-400" />
              )}
              {step.state === 'ready' && <CheckIcon className="size-4 text-success" />}
              {step.state === 'failed' && <XIcon className="size-4 text-red-400" />}
              <span className="flex-1">{t.steps[step.name]}</span>
              <span className="text-xs text-zinc-500">{t.states[step.state]}</span>
            </li>
          ))}
        </ul>
        {preparing?.steps
          .filter((s) => s.detail)
          .map((s) => (
            <p key={s.name} className="text-sm text-red-400">
              {s.detail}
            </p>
          ))}
        {!preparing && !state.notice && (
          <p className="text-sm text-zinc-400">
            {t.connecting}
            <Dots />
          </p>
        )}
        {state.notice && <p className="text-sm text-highlight-text">{state.notice}</p>}
        {(failed || state.notice) && (
          <Button onClick={onRetry}>
            <RotateCcwIcon data-icon="inline-start" />
            {t.retry}
          </Button>
        )}
        <p className="text-xs text-zinc-500">{t.loading}</p>
      </div>
    </Lobby>
  )
}

function Ended({ state, sessionId }: { state: InterviewState; sessionId: string }) {
  const t = useMessages(callMessages)
  const answers = state.entries.filter((e) => e.speaker === 'candidate').length
  return (
    <Stage className="items-center overflow-y-auto p-6">
      <div className="flex w-full max-w-2xl flex-col gap-6 py-10">
        <div className="flex flex-col items-center gap-3 text-center">
          <div className="flex size-14 items-center justify-center rounded-full bg-zinc-800">
            <PhoneOffIcon className="size-6 text-zinc-300" />
          </div>
          <h1 className="font-heading text-2xl font-semibold">{t.ended}</h1>
          <p className="text-sm text-zinc-400" data-testid="ended-summary">
            {state.ended?.failure ?? t.summary(answers, formatClock(state.clock?.elapsedS ?? 0))}
          </p>
          <p className="max-w-md text-xs text-zinc-500">{t.kept}</p>
          <div className="flex gap-2">
            <Button asChild>
              <Link
                to="/interviews/$sessionId"
                params={{ sessionId }}
                data-testid="review-transcript"
              >
                {t.review}
              </Link>
            </Button>
            <Button asChild variant="secondary">
              <Link to="/new-interview">{t.newInterview}</Link>
            </Button>
          </div>
        </div>
        {state.entries.length > 0 && (
          <div className="h-[60vh]">
            <TranscriptPanel entries={state.entries} />
          </div>
        )}
      </div>
    </Stage>
  )
}

function lastOf(entries: Entry[], speaker: Entry['speaker']): Entry | undefined {
  for (let i = entries.length - 1; i >= 0; i--) {
    const entry = entries[i]
    if (entry?.speaker === speaker) return entry
  }
  return undefined
}

/** The meeting, laid out like a video call. */
export function InterviewPage() {
  const t = useMessages(callMessages)
  const meeting = useMessages(meetingMessages)
  const audioText = useMessages(audioMessages)
  const { sessionId } = useParams({ from: '/live-interview/$sessionId' })
  const audio = useAudio()
  const kit = audio.kit
  const { state, answer, endAnswer, endCall, resume, retryStart, dismissNotice } = useInterview(
    sessionId,
    kit,
  )
  const now = useNow(500)
  const [captions, setCaptions] = useState(true)
  const [transcript, setTranscript] = useState(false)
  const [speaking, setSpeaking] = useState(false)

  useEffect(() => kit?.player.subscribe(setSpeaking), [kit])
  const readInterviewer = useCallback(() => kit?.player.level() ?? 0, [kit])
  const interviewerLevel = useAnimatedLevel(readInterviewer, speaking)

  useEffect(() => {
    if (!state.notice) return
    const id = setTimeout(dismissNotice, 8000)
    return () => {
      clearTimeout(id)
    }
  }, [state.notice, dismissNotice])

  const phase = state.phase
  const live = state.status === 'in_progress'
  const answering = live && phase === 'candidate_speaking'
  const canAnswer = live && phase === 'awaiting_candidate'
  const toggleAnswer = useCallback(() => {
    if (answering) endAnswer()
    else if (canAnswer) answer()
  }, [answering, canAnswer, answer, endAnswer])
  useHotkey(' ', toggleAnswer, answering || canAnswer)

  if (!kit) {
    return (
      <Lobby title={t.enableTitle}>
        <div className="flex flex-col gap-4">
          <p className="text-sm text-zinc-400">{t.enableNote}</p>
          <Button onClick={() => void audio.enable()} disabled={audio.enabling}>
            <MicIcon data-icon="inline-start" />
            {t.enable}
          </Button>
          {audio.problem && <p className="text-sm text-red-400">{audioText[audio.problem]}</p>}
        </div>
      </Lobby>
    )
  }
  if (state.ended) return <Ended state={state} sessionId={sessionId} />
  if (state.status === null || state.status === 'ready') {
    return <Preparation state={state} onRetry={retryStart} />
  }

  const remaining = remainingSeconds(state, now)
  const interviewer = lastOf(state.entries, 'interviewer')
  const candidate = lastOf(state.entries, 'candidate')
  const transcribing = live && phase === 'finalizing_transcript'
  const interviewerTalking = speaking || phase === 'interviewer_thinking'
  const caption =
    answering || transcribing
      ? { speaker: meeting.you, text: candidate && !candidate.final ? candidate.text : '' }
      : { speaker: meeting.interviewer, text: interviewerTalking ? (interviewer?.text ?? '') : '' }
  const lastLatency = state.latenciesMs.at(-1)

  let interviewerStatus: ReactNode = null
  if (state.status === 'paused') interviewerStatus = t.pausedShort
  else if (phase === 'interviewer_thinking')
    interviewerStatus = (
      <>
        {t.thinking}
        <Dots />
      </>
    )
  else if (canAnswer) interviewerStatus = t.waiting

  let candidateStatus: ReactNode = null
  if (transcribing)
    candidateStatus = (
      <>
        {t.transcribing}
        <Dots />
      </>
    )
  else if (answering) candidateStatus = t.answering

  return (
    <Stage>
      <header className="flex items-center justify-between px-4 py-3 text-sm">
        <div className="flex items-center gap-2">
          <Wordmark className="text-base" />
          <span className="font-medium">{t.title}</span>
          <span className="text-zinc-500">{t.voice}</span>
        </div>
        <div className="flex items-center gap-3 text-xs text-zinc-500">
          {state.connection === 'closed' && <span className="text-red-400">{t.lost}</span>}
          {lastLatency !== undefined && (
            <span data-testid="latency">
              {t.reply} {(lastLatency / 1000).toFixed(1)} s
            </span>
          )}
        </div>
      </header>

      <main className="flex min-h-0 flex-1 gap-4 px-4">
        <div className="relative flex min-h-0 flex-1 flex-col gap-4">
          <div className="grid min-h-0 flex-1 gap-4 md:grid-cols-2">
            <ParticipantTile
              testId="tile-interviewer"
              name={meeting.interviewer}
              role="ProbeLoop"
              initials="AI"
              tone="interviewer"
              level={interviewerLevel}
              speaking={speaking}
              muted={!speaking}
              status={interviewerStatus}
            />
            <ParticipantTile
              testId="tile-candidate"
              name={meeting.you}
              role={meeting.candidate}
              initials="YOU"
              tone="candidate"
              level={answering ? micLevel(audio.level) : 0}
              speaking={answering}
              muted={!answering}
              status={candidateStatus}
            />
          </div>
          {state.notice && (
            <div className="absolute top-3 left-1/2 z-10 -translate-x-1/2 rounded-xl bg-highlight/15 px-4 py-2 text-sm text-highlight-text ring-1 ring-highlight/30 backdrop-blur">
              {state.notice}
            </div>
          )}
          {state.status === 'paused' && (
            <div className="absolute inset-0 z-10 flex flex-col items-center justify-center gap-4 rounded-2xl bg-black/60 backdrop-blur-sm">
              <p className="text-lg font-medium">{t.paused}</p>
              <Button onClick={resume}>{t.resume}</Button>
            </div>
          )}
          <div className="min-h-14">
            {captions && <Captions speaker={caption.speaker} text={caption.text} />}
          </div>
        </div>
        {transcript && (
          <TranscriptPanel
            entries={state.entries}
            onClose={() => {
              setTranscript(false)
            }}
          />
        )}
      </main>

      <ControlBar
        clock={remaining === null ? '–' : formatClock(remaining)}
        recording={answering}
        answering={answering}
        canAnswer={canAnswer}
        captions={captions}
        transcript={transcript}
        onAnswer={answer}
        onEndAnswer={endAnswer}
        onToggleCaptions={() => {
          setCaptions((on) => !on)
        }}
        onToggleTranscript={() => {
          setTranscript((on) => !on)
        }}
        onEndCall={endCall}
      />
    </Stage>
  )
}
