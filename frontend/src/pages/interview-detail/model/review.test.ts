import { describe, expect, it } from 'vitest'

import type { SessionView, TurnView } from '@/shared/api'

import { openIssues, transcriptReview } from './review'

function answer(seq: number, sources: string[], issues: TurnView['issues'] = []): TurnView {
  return {
    seq,
    speaker: 'candidate',
    text: 'Synthetic answer.',
    elapsed_s: seq,
    audio: null,
    words: [],
    issues,
    status: null,
    topic_id: null,
    revisions: sources.map((source, i) => ({
      number: i + 1,
      text: 'Synthetic answer.',
      source,
      engine_ref: null,
      created_at: i,
    })),
  }
}

const question = (seq: number): TurnView => ({
  seq,
  speaker: 'interviewer',
  text: 'Synthetic question?',
  elapsed_s: seq,
  audio: null,
  words: [],
  revisions: [],
  status: 'complete',
  topic_id: 't1',
})

function session(turns: TurnView[], modality: 'voice' | 'text' = 'voice'): SessionView {
  return {
    id: 'synthetic',
    created_at: 0,
    status: 'ended',
    phase: null,
    difficulty: 'medium',
    language: 'en',
    modality,
    interview_type: 'hr',
    execution_profile: 'cloud',
    profile_id: null,
    snapshot_id: null,
    target_duration_s: 300,
    end_reason: 'user_ended',
    failure: null,
    topics: [],
    coverage: {},
    turns,
  }
}

describe('transcript review', () => {
  it('keeps an issue open until a later pass or an edit replaces the live text', () => {
    expect(openIssues(answer(1, ['stt'], ['reading_missing']))).toEqual(['reading_missing'])
    // The interviewer's reading cannot restore audio that was never recognised.
    expect(openIssues(answer(1, ['stt', 'reconstruction'], ['live_incomplete']))).toEqual([
      'live_incomplete',
    ])
    expect(openIssues(answer(1, ['stt', 'retranscription'], ['live_incomplete']))).toEqual([])
    expect(openIssues(answer(1, ['stt', 'user_edit'], ['reading_missing']))).toEqual([])
  })

  it('numbers flagged answers as the page does and counts live-only ones', () => {
    const review = transcriptReview(
      session([
        question(0),
        answer(1, ['stt', 'reconstruction']),
        question(2),
        answer(3, ['stt'], ['reading_missing']),
        question(4),
        answer(5, ['stt', 'user_edit'], ['live_incomplete']),
      ]),
    )
    expect(review.flagged).toEqual([{ seq: 3, number: 2, issues: ['reading_missing'] }])
    expect(review.liveOnly).toBe(1)
  })

  it('asks nothing about typed answers', () => {
    expect(transcriptReview(session([answer(1, ['stt'])], 'text'))).toEqual({
      flagged: [],
      liveOnly: 0,
    })
  })
})
