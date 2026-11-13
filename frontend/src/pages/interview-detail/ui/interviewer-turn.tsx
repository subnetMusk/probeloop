import type { TurnView } from '@/shared/api'
import { useMessages } from '@/shared/i18n'
import { clock } from '@/shared/lib/format'
import { transcriptMessages } from './messages'
import { TurnAudioButton } from './turn-audio'

/** A question or remark of the interviewer, as a chat bubble on the left. */
export function InterviewerTurn({ turn, question }: { turn: TurnView; question: number }) {
  const t = useMessages(transcriptMessages)
  return (
    <div
      id={`turn-${String(turn.seq)}`}
      data-testid="turn-interviewer"
      className="flex max-w-[min(85%,52rem)] scroll-mt-6 flex-col gap-1.5 self-start rounded-2xl rounded-bl-md bg-muted px-4 py-3"
    >
      <p className="text-xs font-semibold text-foreground/75">
        {t.interviewer}
        <span className="font-normal text-muted-foreground"> · {clock(turn.elapsed_s)}</span>
      </p>
      <p className="text-base leading-relaxed sm:text-lg">
        {turn.text} {turn.status === 'interrupted' && <em>{t.interrupted}</em>}
      </p>
      {turn.audio && (
        <div className="-mx-2">
          <TurnAudioButton src={turn.audio} label={t.question(question)} />
        </div>
      )}
    </div>
  )
}
