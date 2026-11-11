import type { SessionView, TurnView } from '@/shared/api'

export type TranscriptIssue = NonNullable<TurnView['issues']>[number]

/**
 * The issues of an answer that still apply. A later pass over the audio or a manual edit
 * resolves them; the interviewer's reading cannot restore audio that was never recognised.
 */
export function openIssues(turn: TurnView): TranscriptIssue[] {
  const source = turn.revisions.at(-1)?.source
  return source === 'stt' || source === 'reconstruction' ? [...(turn.issues ?? [])] : []
}

export interface TranscriptReview {
  flagged: { seq: number; number: number; issues: TranscriptIssue[] }[]
  liveOnly: number // spoken answers still in their live transcript
}

/** What the candidate should look at before a report assesses a spoken interview. */
export function transcriptReview(session: SessionView): TranscriptReview {
  if (session.modality !== 'voice') return { flagged: [], liveOnly: 0 }
  const answers = [...session.turns]
    .sort((a, b) => a.seq - b.seq)
    .filter((turn) => turn.speaker === 'candidate')
  const flagged = answers.flatMap((turn, index) => {
    const issues = openIssues(turn)
    return issues.length ? [{ seq: turn.seq, number: index + 1, issues }] : []
  })
  const liveOnly = answers.filter(
    (turn) => turn.text.trim() && turn.revisions.at(-1)?.source === 'stt',
  ).length
  return { flagged, liveOnly }
}
