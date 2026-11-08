import { describe, expect, it } from 'vitest'

import type { ServerMessage } from '@/shared/api/types/ws-server'

import { formatClock, initialState, reduce, remainingSeconds } from './state'
import type { InterviewState } from './state'

function play(messages: ServerMessage[], start: InterviewState = initialState): InterviewState {
  return messages.reduce(
    (state, message) => reduce(state, { type: 'server', message, at: 1000 }),
    start,
  )
}

const stateChanged = (
  status: 'ready' | 'in_progress' | 'paused',
  phase: 'interviewer_thinking' | 'awaiting_candidate' | null,
  remaining = 600,
): ServerMessage => ({
  type: 'state.changed',
  seq: 1,
  status,
  phase,
  elapsed_s: 0,
  remaining_s: remaining,
})

describe('interview state', () => {
  it('builds the interviewer turn from deltas, then from the completed move', () => {
    const state = play([
      { type: 'interviewer.text.delta', seq: 2, turn_seq: 0, text: 'Buongiorno. ' },
      { type: 'interviewer.text.delta', seq: 3, turn_seq: 0, text: 'Mi parli' },
    ])
    expect(state.entries).toEqual([
      {
        turnSeq: 0,
        speaker: 'interviewer',
        text: 'Buongiorno. Mi parli',
        final: false,
        incomplete: false,
      },
    ])
    const done = play(
      [
        {
          type: 'interviewer.move.completed',
          seq: 4,
          turn_seq: 0,
          action: 'new_topic',
          topic_id: 't1',
          utterance: 'Buongiorno. Mi parli di lei?',
          fallback: false,
        },
      ],
      state,
    )
    expect(done.entries[0]).toMatchObject({ text: 'Buongiorno. Mi parli di lei?', final: true })
  })

  it('shows the partial transcript, then the recorded answer', () => {
    const state = play([
      { type: 'transcript.partial', seq: 5, turn_seq: 1, text: 'Ho lavorato' },
      { type: 'transcript.partial', seq: 6, turn_seq: 1, text: 'Ho lavorato con Python.' },
    ])
    expect(state.entries).toHaveLength(1)
    expect(state.entries[0]).toMatchObject({
      speaker: 'candidate',
      text: 'Ho lavorato con Python.',
      final: false,
    })
    const recorded = play(
      [
        {
          type: 'candidate.answer.recorded',
          seq: 7,
          turn_seq: 1,
          text: 'Ho lavorato con Python.',
          complete: false,
        },
      ],
      state,
    )
    expect(recorded.entries[0]).toMatchObject({ final: true, incomplete: true })
  })

  it('keeps turns in order even when events interleave', () => {
    const state = play([
      { type: 'interviewer.text.delta', seq: 2, turn_seq: 2, text: 'Seconda domanda?' },
      { type: 'candidate.answer.recorded', seq: 3, turn_seq: 1, text: 'Risposta.', complete: true },
      { type: 'interviewer.text.delta', seq: 1, turn_seq: 0, text: 'Prima domanda?' },
    ])
    expect(state.entries.map((e) => e.turnSeq)).toEqual([0, 1, 2])
  })

  it('tracks preparation until the interview starts', () => {
    const preparing = play([
      stateChanged('ready', null),
      {
        type: 'session.preparing',
        seq: 2,
        progress: 0.333,
        steps: [
          { name: 'language_model', state: 'loading', detail: null },
          { name: 'speech_recognition', state: 'ready', detail: null },
          { name: 'speech_synthesis', state: 'loading', detail: null },
        ],
      },
    ])
    expect(preparing.preparing?.progress).toBe(0.333)
    expect(
      play([stateChanged('in_progress', 'interviewer_thinking')], preparing).preparing,
    ).toBeNull()
  })

  it('turns errors and warnings into notices', () => {
    const state = play([
      { type: 'error', seq: null, code: 'stt_failed', message: 'x', recoverable: true },
    ])
    expect(state.notice).toMatch(/could not be transcribed/)
    const warned = play([{ type: 'answer.time_warning', seq: 3, turn_seq: 1, remaining_s: 119.6 }])
    expect(warned.notice).toBe('About 120 s left for this answer.')
  })

  it('records the end of the session and latencies', () => {
    const ended = play([{ type: 'session.ended', seq: 9, reason: 'completed', failure: null }])
    expect(ended.ended).toEqual({ reason: 'completed', failure: null })
    expect(reduce(ended, { type: 'latency', ms: 2100 }).latenciesMs).toEqual([2100])
  })
})

describe('clock', () => {
  it('counts down only while the interview runs', () => {
    const running = play([stateChanged('in_progress', 'awaiting_candidate', 300)])
    expect(remainingSeconds(running, 1000 + 30_000)).toBe(270)
    const paused = play([stateChanged('paused', 'awaiting_candidate', 300)])
    expect(remainingSeconds(paused, 1000 + 30_000)).toBe(300)
    expect(remainingSeconds(initialState, 0)).toBeNull()
  })

  it('formats minutes and seconds', () => {
    expect(formatClock(605)).toBe('10:05')
    expect(formatClock(59.2)).toBe('1:00')
    expect(formatClock(0)).toBe('0:00')
  })
})
