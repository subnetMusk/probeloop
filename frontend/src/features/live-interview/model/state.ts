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

export interface InterviewState {
  connection: 'connecting' | 'open' | 'closed'
  status: SessionStatus | null
  phase: Phase | null
  clock: { remainingS: number; elapsedS: number; at: number } | null
  preparing: PreparingMessage | null
  entries: Entry[]
  notice: string | null
  ended: { reason: EndReason | null; failure: string | null } | null
  latenciesMs: number[] // "end of answer" click to the start of the reply's audio
}

export type Action =
  | { type: 'connection'; connection: InterviewState['connection'] }
  | { type: 'server'; message: ServerMessage; at: number }
  | { type: 'latency'; ms: number }
  | { type: 'notice'; text: string | null }

export const initialState: InterviewState = {
  connection: 'connecting',
  status: null,
  phase: null,
  clock: null,
  preparing: null,
  entries: [],
  notice: null,
  ended: null,
  latenciesMs: [],
}

const ERROR_TEXT: Record<string, string> = {
  stt_failed: 'Part of your answer could not be transcribed. Its audio is kept.',
  tts_failed: 'A sentence could not be spoken; its text is shown.',
  llm_unavailable: 'The language model did not answer; the interviewer used a fallback phrase.',
}

export function reduce(state: InterviewState, action: Action): InterviewState {
  switch (action.type) {
    case 'connection':
      return { ...state, connection: action.connection }
    case 'latency':
      return { ...state, latenciesMs: [...state.latenciesMs, action.ms] }
    case 'notice':
      return { ...state, notice: action.text }
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
      }
    case 'session.preparing':
      return { ...state, preparing: message, notice: null }
    case 'interviewer.text.delta':
      return upsert(state, message.turn_seq, 'interviewer', (entry) => ({
        ...entry,
        text: entry.text + message.text,
      }))
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
        notice: `About ${Math.round(message.remaining_s)} s left for this answer.`,
      }
    case 'error':
      return { ...state, notice: ERROR_TEXT[message.code] ?? message.message }
    case 'session.ended':
      return { ...state, ended: { reason: message.reason, failure: message.failure } }
    case 'tts.chunk':
    case 'tts.done':
    case 'pong':
      return state
  }
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
  speech_recognition: 'Speech recognition',
  speech_synthesis: "Interviewer's voice",
}
