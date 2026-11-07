import { Link, useParams } from '@tanstack/react-router'
import { CheckIcon, Loader2Icon, MicIcon, PhoneOffIcon, RotateCcwIcon, XIcon } from 'lucide-react'
import type { ReactNode } from 'react'
import { useCallback, useEffect, useState } from 'react'

import { PROBLEM_TEXT, useAudio } from '@/audio/audio-state'
import { Captions } from '@/components/meeting/captions'
import { ControlBar } from '@/components/meeting/control-bar'
import { Dots, ParticipantTile } from '@/components/meeting/participant-tile'
import { TranscriptPanel } from '@/components/meeting/transcript-panel'
import { Button } from '@/components/ui/button'
import { Progress } from '@/components/ui/progress'
import { micLevel, useAnimatedLevel } from '@/hooks/use-animated-level'
import { useHotkey } from '@/hooks/use-hotkey'
import { STEP_TEXT, formatClock, remainingSeconds } from '@/interview/state'
import type { Entry, InterviewState } from '@/interview/state'
import { useInterview } from '@/interview/use-interview'
import { cn } from '@/lib/utils'

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
  const preparing = state.preparing
  const failed = preparing?.steps.some((s) => s.state === 'failed') ?? false
  return (
    <Lobby title={failed ? 'The interview could not start' : 'Joining the interview…'}>
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
              {step.state === 'ready' && <CheckIcon className="size-4 text-emerald-400" />}
              {step.state === 'failed' && <XIcon className="size-4 text-red-400" />}
              <span className="flex-1">{STEP_TEXT[step.name]}</span>
              <span className="text-xs text-zinc-500">{step.state}</span>
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
            Connecting
            <Dots />
          </p>
        )}
        {state.notice && <p className="text-sm text-amber-300">{state.notice}</p>}
        {(failed || state.notice) && (
          <Button onClick={onRetry}>
            <RotateCcwIcon data-icon="inline-start" />
            Try again
          </Button>
        )}
        <p className="text-xs text-zinc-500">
          Loading the language model can take a minute the first time.
        </p>
      </div>
    </Lobby>
  )
}

function Ended({ state, sessionId }: { state: InterviewState; sessionId: string }) {
  const answers = state.entries.filter((e) => e.speaker === 'candidate').length
  return (
    <Stage className="items-center overflow-y-auto p-6">
      <div className="flex w-full max-w-2xl flex-col gap-6 py-10">
        <div className="flex flex-col items-center gap-3 text-center">
          <div className="flex size-14 items-center justify-center rounded-full bg-zinc-800">
            <PhoneOffIcon className="size-6 text-zinc-300" />
          </div>
          <h1 className="font-heading text-2xl font-semibold">The interview has ended</h1>
          <p className="text-sm text-zinc-400" data-testid="ended-summary">
            {state.ended?.failure ??
              `${answers} ${answers === 1 ? 'answer' : 'answers'} · ${formatClock(state.clock?.elapsedS ?? 0)} of conversation`}
          </p>
          <p className="max-w-md text-xs text-zinc-500">
            The full transcript and the audio of the whole conversation are kept with the session.
            Your answers are now transcribed again, more accurately: review them before the report.
          </p>
          <div className="flex gap-2">
            <Button asChild>
              <Link
                to="/sessions/$sessionId"
                params={{ sessionId }}
                data-testid="review-transcript"
              >
                Review the transcript
              </Link>
            </Button>
            <Button asChild variant="secondary">
              <Link to="/">New interview</Link>
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
  const { sessionId } = useParams({ from: '/interview/$sessionId' })
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
      <Lobby title="Enable the microphone to join">
        <div className="flex flex-col gap-4">
          <p className="text-sm text-zinc-400">
            The interview is spoken: the browser needs the microphone, and a click to play audio.
          </p>
          <Button onClick={() => void audio.enable()} disabled={audio.enabling}>
            <MicIcon data-icon="inline-start" />
            Enable microphone and audio
          </Button>
          {audio.problem && <p className="text-sm text-red-400">{PROBLEM_TEXT[audio.problem]}</p>}
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
      ? { speaker: 'You', text: candidate && !candidate.final ? candidate.text : '' }
      : { speaker: 'Interviewer', text: interviewerTalking ? (interviewer?.text ?? '') : '' }
  const lastLatency = state.latenciesMs.at(-1)

  let interviewerStatus: ReactNode = null
  if (state.status === 'paused') interviewerStatus = 'Paused'
  else if (phase === 'interviewer_thinking')
    interviewerStatus = (
      <>
        Thinking
        <Dots />
      </>
    )
  else if (canAnswer) interviewerStatus = 'Waiting for your answer'

  let candidateStatus: ReactNode = null
  if (transcribing)
    candidateStatus = (
      <>
        Transcribing
        <Dots />
      </>
    )
  else if (answering) candidateStatus = 'Answering'

  return (
    <Stage>
      <header className="flex items-center justify-between px-4 py-3 text-sm">
        <div className="flex items-center gap-2">
          <span className="flex size-7 items-center justify-center rounded-lg bg-indigo-500 font-heading font-semibold text-white">
            P
          </span>
          <span className="font-medium">Mock interview</span>
          <span className="text-zinc-500">· voice</span>
        </div>
        <div className="flex items-center gap-3 text-xs text-zinc-500">
          {state.connection === 'closed' && <span className="text-red-400">Connection lost</span>}
          {lastLatency !== undefined && (
            <span data-testid="latency">reply after {(lastLatency / 1000).toFixed(1)} s</span>
          )}
        </div>
      </header>

      <main className="flex min-h-0 flex-1 gap-4 px-4">
        <div className="relative flex min-h-0 flex-1 flex-col gap-4">
          <div className="grid min-h-0 flex-1 gap-4 md:grid-cols-2">
            <ParticipantTile
              testId="tile-interviewer"
              name="Interviewer"
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
              name="You"
              role="Candidate"
              initials="YOU"
              tone="candidate"
              level={answering ? micLevel(audio.level) : 0}
              speaking={answering}
              muted={!answering}
              status={candidateStatus}
            />
          </div>
          {state.notice && (
            <div className="absolute top-3 left-1/2 z-10 -translate-x-1/2 rounded-xl bg-amber-500/15 px-4 py-2 text-sm text-amber-200 ring-1 ring-amber-400/30 backdrop-blur">
              {state.notice}
            </div>
          )}
          {state.status === 'paused' && (
            <div className="absolute inset-0 z-10 flex flex-col items-center justify-center gap-4 rounded-2xl bg-black/60 backdrop-blur-sm">
              <p className="text-lg font-medium">The interview is paused</p>
              <Button onClick={resume}>Resume</Button>
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
