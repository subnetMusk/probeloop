/**
 * Client-side state of a live interview, rebuilt from the server's events. The server holds the
 * authoritative state; this reducer only keeps what the page shows. Pure, so it is unit-tested.
 */
import type {
  EndReason,
  Phase,
  PreparingMessage,
  ServerMessage,
  SessionStatus,
} from '@/shared/api/types/ws-server'

export interface Entry {
  turnSeq: number
  speaker: 'interviewer' | 'candidate'
  text: string
  final: boolean // false while the text is still streaming or being recognised
  incomplete: boolean // part of a spoken answer could not be transcribed
}

/**
 * Where the reply to a spoken answer is, from "end of answer" to the first sound of the next
 * question: the audio reaches the server, the answer is transcribed, the interviewer writes the
 * question, and its first sentence is synthesised.
 */
export type ReplyStage = 'sending' | 'transcribing' | 'thinking' | 'voicing'

export interface ReplyProgress {
  stage: ReplyStage
  startedAt: number // performance time of "end of answer"
  stepAt: number // when the shown step began; "voicing" continues the "thinking" step
}

/**
 * Something the page should tell the candidate. The page words it in the interface language:
 * an error by its code (or the server's text for an unknown one), a time warning by its seconds.
 */
export type Notice =
  { kind: 'error'; code: string; message: string } | { kind: 'answer_time'; remainingS: number }

export interface InterviewState {
  connection: 'connecting' | 'open' | 'closed'
  status: SessionStatus | null
  phase: Phase | null
  clock: { remainingS: number; elapsedS: number; at: number } | null
  preparing: PreparingMessage | null
  preparingAt: number | null // when the current preparation began
  reply: ReplyProgress | null
  entries: Entry[]
  notice: Notice | null
  ended: { reason: EndReason | null; failure: string | null } | null
  latenciesMs: number[] // "end of answer" click to the start of the reply's audio
}

export type Action =
  | { type: 'connection'; connection: InterviewState['connection'] }
  | { type: 'server'; message: ServerMessage; at: number }
  | { type: 'latency'; ms: number }
  | { type: 'reply'; at: number }
  | { type: 'dismiss' }

export const initialState: InterviewState = {
  connection: 'connecting',
  status: null,
  phase: null,
  clock: null,
  preparing: null,
  preparingAt: null,
  reply: null,
  entries: [],
  notice: null,
  ended: null,
  latenciesMs: [],
}

export function reduce(state: InterviewState, action: Action): InterviewState {
  switch (action.type) {
    case 'connection':
      return { ...state, connection: action.connection }
    case 'latency': // the reply's audio has started
      return { ...state, latenciesMs: [...state.latenciesMs, action.ms], reply: null }
    case 'reply':
      return {
        ...state,
        reply: { stage: 'sending', startedAt: action.at, stepAt: action.at },
      }
    case 'dismiss':
      return { ...state, notice: null }
    case 'server':
      return onMessage(state, action.message, action.at)
  }
}

function onMessage(state: InterviewState, message: ServerMessage, at: number): InterviewState {
  switch (message.type) {
    case 'state.changed':
      return {
        ...state,
        status: message.status,
        phase: message.phase,
        clock: { remainingS: message.remaining_s, elapsedS: message.elapsed_s, at },
        preparing: message.status === 'ready' ? state.preparing : null,
        preparingAt: message.status === 'ready' ? state.preparingAt : null,
        reply: nextReply(state.reply, message.status, message.phase, at),
      }
    case 'session.preparing':
      return {
        ...state,
        preparing: message,
        // A new attempt after a failure starts the clock again.
        preparingAt:
          state.preparingAt === null || state.preparing?.steps.some((s) => s.state === 'failed')
            ? at
            : state.preparingAt,
        notice: null,
      }
    case 'interviewer.text.delta': {
      const next = upsert(state, message.turn_seq, 'interviewer', (entry) => ({
        ...entry,
        text: entry.text + message.text,
      }))
      return state.reply?.stage === 'thinking'
        ? { ...next, reply: { ...state.reply, stage: 'voicing' } }
        : next
    }
    case 'interviewer.move.completed':
      return upsert(state, message.turn_seq, 'interviewer', (entry) => ({
        ...entry,
        text: message.utterance,
        final: true,
      }))
    case 'transcript.partial':
      return upsert(state, message.turn_seq, 'candidate', (entry) => ({
        ...entry,
        text: message.text,
      }))
    case 'candidate.answer.recorded':
      return upsert(state, message.turn_seq, 'candidate', (entry) => ({
        ...entry,
        text: message.text,
        final: true,
        incomplete: !message.complete,
      }))
    case 'answer.time_warning':
      return {
        ...state,
        notice: { kind: 'answer_time', remainingS: message.remaining_s },
      }
    case 'error':
      return {
        ...state,
        notice: { kind: 'error', code: message.code, message: message.message },
      }
    case 'session.ended':
      return { ...state, ended: { reason: message.reason, failure: message.failure } }
    case 'tts.chunk':
    case 'tts.done':
    case 'pong':
      return state
  }
}

function nextReply(
  reply: ReplyProgress | null,
  status: SessionStatus,
  phase: Phase | null,
  at: number,
): ReplyProgress | null {
  if (status !== 'in_progress') return null
  switch (phase) {
    case 'finalizing_transcript':
      if (!reply) return { stage: 'transcribing', startedAt: at, stepAt: at }
      return reply.stage === 'sending' ? { ...reply, stage: 'transcribing', stepAt: at } : reply
    case 'interviewer_thinking':
      // Without a reply in progress this is the first question, which the preparation covered.
      if (!reply || reply.stage === 'thinking' || reply.stage === 'voicing') return reply
      return { ...reply, stage: 'thinking', stepAt: at }
    case 'interviewer_speaking':
      return reply // the move is written; its audio may not have started yet
    default:
      return null
  }
}

/**
 * How far a step expected to take `expectedS` has probably gone after `elapsedS`: quickly at
 * first, then more slowly, and never complete before the step really ends.
 */
export function easedFill(elapsedS: number, expectedS: number): number {
  if (elapsedS <= 0) return 0
  return Math.min(0.95, 1 - Math.exp(-elapsedS / Math.max(expectedS, 0.1)))
}

export type StepState = 'done' | 'active' | 'pending'

export interface ShownStep<Name extends string> {
  name: Name
  state: StepState
  fill: number // 0..1
}

export const REPLY_STEPS = ['audio', 'transcript', 'question'] as const
export type ReplyStep = (typeof REPLY_STEPS)[number]

const STEP_OF: Record<ReplyStage, number> = { sending: 0, transcribing: 1, thinking: 2, voicing: 2 }

/** The steps of a reply at `now`, each with the share of it that is probably done. */
export function replySteps(
  reply: ReplyProgress,
  now: number,
  latenciesMs: number[],
): ShownStep<ReplyStep>[] {
  const current = STEP_OF[reply.stage]
  // The question's step lasts about as long as earlier replies, less sending and transcribing.
  const typicalS = latenciesMs.length ? median(latenciesMs) / 1000 - 1.2 : 4.5
  const expected = [0.4, 1.0, Math.max(2, typicalS)]
  const elapsedS = Math.max(0, (now - reply.stepAt) / 1000)
  return REPLY_STEPS.map((name, i) => {
    if (i < current) return { name, state: 'done', fill: 1 }
    if (i > current) return { name, state: 'pending', fill: 0 }
    let fill = easedFill(elapsedS, expected[i] ?? 1)
    // The question is written: only the audio of its first sentence is missing.
    if (reply.stage === 'voicing') fill = Math.max(fill, 0.85)
    return { name, state: 'active', fill }
  })
}

export type PreparationStepName = PreparingMessage['steps'][number]['name']

export interface PreparationProgress {
  name: PreparationStepName
  state: StepState | 'failed'
  fill: number // 0..1
  detail: string | null
}

/** The steps of the preparation at `now`; a step still loading fills with the time it takes. */
export function preparationSteps(state: InterviewState, now: number): PreparationProgress[] {
  const elapsedS = state.preparingAt === null ? 0 : Math.max(0, (now - state.preparingAt) / 1000)
  return (state.preparing?.steps ?? []).map((step) => {
    if (step.state === 'ready') return { name: step.name, state: 'done', fill: 1, detail: null }
    if (step.state === 'failed')
      return { name: step.name, state: 'failed', fill: 1, detail: step.detail }
    return { name: step.name, state: 'active', fill: easedFill(elapsedS, 12), detail: null }
  })
}

function median(values: number[]): number {
  const sorted = [...values].sort((a, b) => a - b)
  const middle = Math.floor(sorted.length / 2)
  if (sorted.length % 2) return sorted[middle] ?? 0
  return ((sorted[middle - 1] ?? 0) + (sorted[middle] ?? 0)) / 2
}

function upsert(
  state: InterviewState,
  turnSeq: number,
  speaker: Entry['speaker'],
  change: (entry: Entry) => Entry,
): InterviewState {
  const index = state.entries.findIndex((e) => e.turnSeq === turnSeq && e.speaker === speaker)
  const current = state.entries[index] ?? {
    turnSeq,
    speaker,
    text: '',
    final: false,
    incomplete: false,
  }
  const entries = [...state.entries]
  if (index === -1) {
    entries.push(change(current))
    entries.sort((a, b) => a.turnSeq - b.turnSeq)
  } else {
    entries[index] = change(current)
  }
  return { ...state, entries }
}

/** Seconds left in the interview at `now` (performance time), counting down between updates. */
export function remainingSeconds(state: InterviewState, now: number): number | null {
  if (!state.clock) return null
  const running = state.status === 'in_progress'
  const passed = running ? (now - state.clock.at) / 1000 : 0
  return Math.max(0, state.clock.remainingS - passed)
}

export function formatClock(seconds: number): string {
  const whole = Math.ceil(seconds)
  return `${Math.floor(whole / 60)}:${String(whole % 60).padStart(2, '0')}`
}

export const PHASE_TEXT: Record<Phase, string> = {
  interviewer_thinking: 'The interviewer is thinking',
  interviewer_speaking: 'The interviewer is speaking',
  awaiting_candidate: 'Your turn: press Answer when ready',
  candidate_speaking: 'You are answering',
  finalizing_transcript: 'Transcribing your answer',
}

export const STEP_TEXT: Record<PreparingMessage['steps'][number]['name'], string> = {
  language_model: 'Language model',
  stated_limits: 'Stated limits',
  speech_recognition: 'Speech recognition',
  speech_synthesis: "Interviewer's voice",
}
