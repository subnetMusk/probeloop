import type { TurnView } from '@/shared/api'

export interface ConversationBlock {
  number: number
  questions: TurnView[]
  answers: { number: number; turn: TurnView }[]
}

/** Consecutive prompts stay with the answer they prompted; trailing prompts are kept. */
export function conversationOf(turns: readonly TurnView[]): ConversationBlock[] {
  const blocks: ConversationBlock[] = []
  let answerNumber = 0
  for (const turn of [...turns].sort((a, b) => a.seq - b.seq)) {
    let current = blocks.at(-1)
    if (!current || (turn.speaker === 'interviewer' && current.answers.length > 0)) {
      current = { number: blocks.length + 1, questions: [], answers: [] }
      blocks.push(current)
    }
    if (turn.speaker === 'interviewer') current.questions.push(turn)
    else current.answers.push({ number: ++answerNumber, turn })
  }
  return blocks
}
