import { Link, useNavigate, useParams } from '@tanstack/react-router'
import { MicIcon, PhoneOffIcon, RotateCcwIcon } from 'lucide-react'
import type { ReactNode } from 'react'
import { useCallback, useEffect, useState } from 'react'

import { audioMessages, useAudio } from '@/shared/lib/audio'
import { Captions } from '@/widgets/meeting'
import { ControlBar } from '@/widgets/meeting'
import { Dots, ParticipantTile, ProgressRing, StepIcon } from '@/widgets/meeting'
import { TranscriptPanel } from '@/widgets/meeting'
import { localizeProblem } from '@/shared/api'
import { Button } from '@/shared/ui/button'
import { Wordmark } from '@/shared/ui/wordmark'
import { useLanguage } from '@/shared/lib/preferences'
import { measurement } from '@/shared/lib/format'
import { micLevel, useAnimatedLevel } from '@/shared/lib/hooks'
import { useHotkey } from '@/shared/lib/hooks'
import {
  formatClock,
  preparationSteps,
  remainingSeconds,
  replySteps,
} from '@/features/live-interview'
import type { Entry, InterviewState, Notice } from '@/features/live-interview'
import { useInterview } from '@/features/live-interview'
import { cn } from '@/shared/lib/utils'
import { useMessages } from '@/shared/i18n'
import { meetingMessages } from '@/widgets/meeting'
import { callMessages } from './messages'

/** The notice in the interface language. */
function useNoticeText(notice: Notice | null): string | null {
  const t = useMessages(callMessages)
  const language = useLanguage()
  if (!notice) return null
  if (notice.kind === 'answer_time') return t.answerTime(notice.remainingS)
  const notices: Record<string, string> = t.notices
  return notices[notice.code] ?? localizeProblem(notice.message, language)
}

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

/**
 * Between "start" and the first question: the interviewer's avatar, with one arc of the ring per
 * thing being loaded, and the same steps listed below with what each one is for.
 */
function Preparation({ state, onRetry }: { state: InterviewState; onRetry: () => void }) {
  const t = useMessages(callMessages)
  const language = useLanguage()
  const now = useNow(250)
  const steps = preparationSteps(state, now)
  const notice = useNoticeText(state.notice)
  const failed = steps.some((s) => s.state === 'failed')
  const elapsedS = state.preparingAt === null ? 0 : (now - state.preparingAt) / 1000
  const stateText = {
    done: t.states.ready,
    active: t.states.loading,
    failed: t.states.failed,
    pending: '',
  }
  const ready = steps.filter((s) => s.state === 'done').length
  return (
    <Stage className="items-center overflow-y-auto p-6">
      <div
        className="my-auto flex w-full max-w-md flex-col items-center gap-6 py-6 text-center"
        data-testid="preparation"
        data-failed={failed}
      >
        <div className="relative flex size-44 items-center justify-center">
          <ProgressRing segments={steps} dimmed={failed} className="absolute inset-0 size-full" />
          <span
            aria-hidden
            className={cn(
              'absolute size-24 rounded-full bg-gradient-to-br from-brand to-highlight opacity-30 blur-md',
              !failed && 'motion-safe:animate-pulse',
            )}
          />
          <div
            className={cn(
              'relative flex size-24 items-center justify-center rounded-full bg-gradient-to-br from-brand to-highlight text-2xl font-semibold text-white shadow-lg transition-[filter] duration-500',
              failed && 'grayscale',
            )}
          >
            AI
          </div>
        </div>

        <div className="flex flex-col gap-2">
          <h1 className="font-heading text-xl font-semibold">{failed ? t.failed : t.joining}</h1>
          <p className="text-sm text-zinc-400">{t.preparingNote}</p>
        </div>

        {steps.length === 0 && !state.notice && (
          <p className="text-sm text-zinc-400">
            {t.connecting}
            <Dots />
          </p>
        )}

        {steps.length > 0 && (
          <ol
            className="w-full divide-y divide-white/5 overflow-hidden rounded-2xl bg-zinc-900/80 text-left ring-1 ring-white/5"
            data-testid="preparation-progress"
            role="progressbar"
            aria-label={t.joining}
            aria-valuemin={0}
            aria-valuemax={steps.length}
            aria-valuenow={ready}
          >
            {steps.map((step) => (
              <li
                key={step.name}
                className="flex items-start gap-3 px-4 py-3"
                data-testid={`step-${step.name}`}
                data-state={step.state}
              >
                <StepIcon state={step.state} className="mt-0.5" />
                <div className="min-w-0 flex-1">
                  <p
                    className={cn(
                      'text-sm',
                      step.state === 'active' ? 'font-medium text-white' : 'text-zinc-200',
                    )}
                  >
                    {t.steps[step.name]}
                  </p>
                  <p
                    className={cn(
                      'text-xs',
                      step.state === 'failed' ? 'text-red-400' : 'text-zinc-500',
                    )}
                  >
                    {step.detail ? localizeProblem(step.detail, language) : t.stepNotes[step.name]}
                  </p>
                </div>
                <span className="pt-0.5 text-xs text-zinc-500">{stateText[step.state]}</span>
              </li>
            ))}
          </ol>
        )}

        {/* A failed step already says why; other problems (a lost connection) come as notices. */}
        {notice && !failed && <p className="text-sm text-highlight-text">{notice}</p>}
        {(failed || state.notice) && (
          <Button onClick={onRetry}>
            <RotateCcwIcon data-icon="inline-start" />
            {t.retry}
          </Button>
        )}
        {!failed && elapsedS > 8 && (
          <p className="text-xs text-zinc-500 motion-safe:animate-in motion-safe:fade-in">
            {t.loading}
          </p>
        )}
      </div>
    </Stage>
  )
}

/**
 * The end of the call. A completed call opens the transcript review, which summarises it; a
 * failed one stays here with its reason and a way to the saved transcript.
 */
function Ended({ state, sessionId }: { state: InterviewState; sessionId: string }) {
  const t = useMessages(callMessages)
  const navigate = useNavigate()
  const failure = state.ended?.failure
  useEffect(() => {
    if (!failure)
      void navigate({
        to: '/interviews/$sessionId',
        params: { sessionId },
        search: { ended: true },
        replace: true,
      })
  }, [failure, navigate, sessionId])
  if (!failure)
    return (
      <Stage className="items-center justify-center">
        <Dots />
      </Stage>
    )
  return (
    <Stage className="items-center overflow-y-auto p-6">
      <div className="flex w-full max-w-2xl flex-col items-center gap-3 py-10 text-center">
        <div className="flex size-14 items-center justify-center rounded-full bg-zinc-800">
          <PhoneOffIcon className="size-6 text-zinc-300" />
        </div>
        <h1 className="font-heading text-2xl font-semibold">{t.ended}</h1>
        <p className="text-sm text-zinc-400" data-testid="ended-summary">
          {failure}
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
  const language = useLanguage()
  const { sessionId } = useParams({ from: '/live-interview/$sessionId' })
  const audio = useAudio()
  const kit = audio.kit
  const { state, answer, endAnswer, endCall, resume, retryStart, dismissNotice } = useInterview(
    sessionId,
    kit,
  )
  const now = useNow(state.reply ? 200 : 500)
  const notice = useNoticeText(state.notice)
  const [captions, setCaptions] = useState(true)
  const [transcript, setTranscript] = useState(false)
  const [speaking, setSpeaking] = useState(false)

  useEffect(() => kit?.player.subscribe(setSpeaking), [kit])
  const readInterviewer = useCallback(() => kit?.player.level() ?? 0, [kit])
  const interviewerLevel = useAnimatedLevel(readInterviewer, speaking)
  const interviewerVoice = useCallback(
    (target: Uint8Array<ArrayBuffer>) => kit?.player.spectrum(target) ?? false,
    [kit],
  )
  const candidateVoice = useCallback(
    (target: Uint8Array<ArrayBuffer>) => kit?.microphone.spectrum(target) ?? false,
    [kit],
  )

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
  // Between an answer and the next question the ring around the interviewer shows the steps;
  // the captions stay empty, so the question is not read before it is heard.
  const reply = state.reply && !speaking ? replySteps(state.reply, now, state.latenciesMs) : null
  const replyStep = reply?.find((s) => s.state === 'active')
  const caption =
    answering || transcribing
      ? { speaker: meeting.you, text: candidate && !candidate.final ? candidate.text : '' }
      : {
          speaker: meeting.interviewer,
          text: interviewerTalking && !reply ? (interviewer?.text ?? '') : '',
        }
  const lastLatency = state.latenciesMs.at(-1)

  let interviewerStatus: ReactNode = null
  if (state.status === 'paused') interviewerStatus = t.pausedShort
  else if (replyStep)
    interviewerStatus = (
      <span role="status" data-testid="reply-step" data-step={replyStep.name}>
        {t.replySteps[replyStep.name]}
        <Dots />
      </span>
    )
  else if (phase === 'interviewer_thinking')
    interviewerStatus = (
      <>
        {t.thinking}
        <Dots />
      </>
    )
  else if (canAnswer) interviewerStatus = t.waiting

  let candidateStatus: ReactNode = null
  if (transcribing && !reply)
    // with a reply in progress the interviewer's ring shows this step
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
          <span className="hidden font-medium sm:inline">{t.title}</span>
          <span className="hidden text-zinc-500 sm:inline">{t.voice}</span>
        </div>
        <div className="flex items-center gap-3 text-xs text-zinc-500">
          {state.connection === 'closed' && <span className="text-red-400">{t.lost}</span>}
          {lastLatency !== undefined && (
            <span data-testid="latency">
              {t.reply} {measurement(lastLatency / 1000, language)} s
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
              progress={reply}
              voice={interviewerVoice}
              listening={answering}
            />
            <ParticipantTile
              testId="tile-candidate"
              name={meeting.you}
              role={meeting.candidate}
              initials={meeting.you.toUpperCase()}
              tone="candidate"
              level={answering ? micLevel(audio.level) : 0}
              speaking={answering}
              muted={!answering}
              status={candidateStatus}
              voice={candidateVoice}
              listening={speaking}
            />
          </div>
          {notice && (
            <div className="absolute top-3 left-1/2 z-10 -translate-x-1/2 rounded-xl bg-highlight/15 px-4 py-2 text-sm text-highlight-text ring-1 ring-highlight/30 backdrop-blur">
              {notice}
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
