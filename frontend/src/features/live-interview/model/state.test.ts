import { describe, expect, it } from 'vitest'

import type { ServerMessage } from '@/shared/api/types/ws-server'

import {
  easedFill,
  formatClock,
  initialState,
  preparationSteps,
  reduce,
  remainingSeconds,
  replySteps,
} from './state'
import type { InterviewState } from './state'

function play(messages: ServerMessage[], start: InterviewState = initialState): InterviewState {
  return messages.reduce(
    (state, message) => reduce(state, { type: 'server', message, at: 1000 }),
    start,
  )
}

const stateChanged = (
  status: 'ready' | 'in_progress' | 'paused',
  phase:
    | 'interviewer_thinking'
    | 'interviewer_speaking'
    | 'awaiting_candidate'
    | 'finalizing_transcript'
    | null,
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
    expect(state.notice).toEqual({ kind: 'error', code: 'stt_failed', message: 'x' })
    const warned = play([{ type: 'answer.time_warning', seq: 3, turn_seq: 1, remaining_s: 119.6 }])
    expect(warned.notice).toEqual({ kind: 'answer_time', remainingS: 119.6 })
    expect(reduce(warned, { type: 'dismiss' }).notice).toBeNull()
  })

  it('records the end of the session and latencies', () => {
    const ended = play([{ type: 'session.ended', seq: 9, reason: 'completed', failure: null }])
    expect(ended.ended).toEqual({ reason: 'completed', failure: null })
    expect(reduce(ended, { type: 'latency', ms: 2100 }).latenciesMs).toEqual([2100])
  })
})

function at(state: InterviewState, message: ServerMessage, time: number): InterviewState {
  return reduce(state, { type: 'server', message, at: time })
}

describe('reply progress', () => {
  const answered = reduce(play([stateChanged('in_progress', 'awaiting_candidate')]), {
    type: 'reply',
    at: 2000,
  })

  it('follows the reply from the end of the answer to its first sound', () => {
    expect(answered.reply).toEqual({ stage: 'sending', startedAt: 2000, stepAt: 2000 })
    const transcribing = at(answered, stateChanged('in_progress', 'finalizing_transcript'), 2300)
    expect(transcribing.reply).toMatchObject({ stage: 'transcribing', stepAt: 2300 })
    const thinking = at(transcribing, stateChanged('in_progress', 'interviewer_thinking'), 3000)
    expect(thinking.reply).toMatchObject({ stage: 'thinking', stepAt: 3000 })
    const voicing = at(
      thinking,
      { type: 'interviewer.text.delta', seq: 4, turn_seq: 2, text: 'Come' },
      6000,
    )
    // The written question continues the same step: only its audio is missing.
    expect(voicing.reply).toMatchObject({ stage: 'voicing', stepAt: 3000 })
    const written = at(voicing, stateChanged('in_progress', 'interviewer_speaking'), 6500)
    expect(written.reply?.stage).toBe('voicing')
    expect(reduce(written, { type: 'latency', ms: 4800 }).reply).toBeNull()
  })

  it('stops when the interview pauses or the reply has no audio', () => {
    expect(at(answered, stateChanged('paused', 'awaiting_candidate'), 2500).reply).toBeNull()
    expect(at(answered, stateChanged('in_progress', 'awaiting_candidate'), 2500).reply).toBeNull()
  })

  it('leaves the first question to the preparation', () => {
    const first = play([stateChanged('in_progress', 'interviewer_thinking')])
    expect(first.reply).toBeNull()
  })

  it('fills the running step with time, never completely', () => {
    expect(easedFill(0, 1)).toBe(0)
    expect(easedFill(1, 1)).toBeCloseTo(0.632, 2)
    expect(easedFill(60, 1)).toBe(0.95)
    const reply = { stage: 'thinking' as const, startedAt: 0, stepAt: 1000 }
    const steps = replySteps(reply, 1000 + 3800, [5000, 6000, 5200])
    expect(steps.map((s) => [s.name, s.state, s.fill])).toEqual([
      ['audio', 'done', 1],
      ['transcript', 'done', 1],
      ['question', 'active', easedFill(3.8, 5.2 - 1.2)],
    ])
    const voicing = replySteps({ ...reply, stage: 'voicing' }, 1100, [])
    expect(voicing[2]?.fill).toBe(0.85)
  })
})

describe('preparation progress', () => {
  it('fills loading steps with time and restarts the clock after a failure', () => {
    const loading = at(
      play([stateChanged('ready', null)]),
      {
        type: 'session.preparing',
        seq: 2,
        progress: 0.5,
        steps: [
          { name: 'language_model', state: 'ready', detail: null },
          { name: 'stated_limits', state: 'loading', detail: null },
        ],
      },
      5000,
    )
    expect(loading.preparingAt).toBe(5000)
    expect(preparationSteps(loading, 5000 + 12_000)).toEqual([
      { name: 'language_model', state: 'done', fill: 1, detail: null },
      { name: 'stated_limits', state: 'active', fill: easedFill(12, 12), detail: null },
    ])
    const failed = at(
      loading,
      {
        type: 'session.preparing',
        seq: 3,
        progress: 0.5,
        steps: [
          { name: 'language_model', state: 'ready', detail: null },
          { name: 'stated_limits', state: 'failed', detail: 'Jev key missing' },
        ],
      },
      9000,
    )
    expect(failed.preparingAt).toBe(5000)
    expect(preparationSteps(failed, 9000)[1]).toMatchObject({
      state: 'failed',
      detail: 'Jev key missing',
    })
    const retried = at(
      failed,
      {
        type: 'session.preparing',
        seq: 4,
        progress: 0,
        steps: [{ name: 'stated_limits', state: 'loading', detail: null }],
      },
      20_000,
    )
    expect(retried.preparingAt).toBe(20_000)
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
