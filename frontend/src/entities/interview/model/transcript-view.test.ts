import { expect, it } from 'vitest'
import type { TurnView } from '@/shared/api'
import { conversationOf } from './transcript-view'

const turn = (seq: number, speaker: TurnView['speaker']): TurnView => ({
  seq,
  speaker,
  text: `Text ${String(seq)}`,
  elapsed_s: seq,
  audio: null,
  words: [],
  revisions: [],
  status: null,
  topic_id: null,
})

it('keeps follow-up prompts with their answers and preserves an unanswered closing prompt', () => {
  const blocks = conversationOf([
    turn(4, 'candidate'),
    turn(0, 'interviewer'),
    turn(1, 'interviewer'),
    turn(2, 'candidate'),
    turn(3, 'interviewer'),
    turn(5, 'interviewer'),
  ])
  expect(blocks.map((block) => block.questions.map((question) => question.seq))).toEqual([
    [0, 1],
    [3],
    [5],
  ])
  expect(
    blocks.flatMap((block) => block.answers.map((answer) => [answer.number, answer.turn.seq])),
  ).toEqual([
    [1, 2],
    [2, 4],
  ])
})

it('keeps an answer without a preceding prompt and accepts an empty conversation', () => {
  expect(conversationOf([])).toEqual([])
  expect(conversationOf([turn(1, 'candidate')])[0]?.answers[0]?.number).toBe(1)
})
