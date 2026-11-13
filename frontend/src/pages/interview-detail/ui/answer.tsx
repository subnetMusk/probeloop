import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { PencilIcon, TriangleAlertIcon } from 'lucide-react'

import { api } from '@/shared/api'
import type { SessionView, TurnView, WordView } from '@/shared/api'
import { useMessages } from '@/shared/i18n'
import { clock } from '@/shared/lib/format'
import { cn } from '@/shared/lib/utils'
import { Badge } from '@/shared/ui/badge'
import { Button } from '@/shared/ui/button'
import { RequiredMark } from '@/shared/ui/required-mark'
import { Textarea } from '@/shared/ui/textarea'
import { openIssues } from '../model/review'
import { transcriptMessages } from './messages'
import { TurnAudioButton } from './turn-audio'
import { useTurnAudio } from './turn-audio-context'

/** Seconds of audio played before and after a doubtful word, so it is heard in context. */
const WORD_MARGIN_S = 0.6

const DOUBTFUL =
  'rounded-sm bg-amber-100 px-0.5 text-inherit underline decoration-amber-600 decoration-dotted dark:bg-amber-500/20'

/**
 * The recognised words; those below one half of confidence are highlighted. With `onListen`
 * a highlighted word is a button that plays the audio around it.
 */
export function Words({
  words,
  onListen,
}: {
  words: WordView[]
  onListen?: (word: WordView) => void
}) {
  const t = useMessages(transcriptMessages)
  return (
    <>
      {words.map((word, i) => (
        <span key={i}>
          {i > 0 && ' '}
          {word.probability !== null && word.probability < 0.5 ? (
            <mark
              title={t.confidence(Math.round(word.probability * 100))}
              data-testid="doubtful-word"
              className={DOUBTFUL}
            >
              {onListen ? (
                <button
                  type="button"
                  className="cursor-pointer rounded-sm underline-offset-2 focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none"
                  aria-label={t.listenWord(word.text, Math.round(word.probability * 100))}
                  onClick={() => {
                    onListen(word)
                  }}
                >
                  {word.text}
                </button>
              ) : (
                word.text
              )}
            </mark>
          ) : (
            word.text
          )}
        </span>
      ))}
    </>
  )
}

/** An answer as a chat bubble: its words, its audio, its open issues and an in-place editor. */
export function Answer({
  session,
  turn,
  number,
}: {
  session: SessionView
  turn: TurnView
  number: number
}) {
  const t = useMessages(transcriptMessages)
  const client = useQueryClient()
  const player = useTurnAudio()
  const [draft, setDraft] = useState<string | null>(null)
  const save = useMutation({
    mutationFn: (text: string) => api.editAnswer(session.id, turn.seq, text),
    onSuccess: (updated) => {
      client.setQueryData(['session', session.id], updated)
      setDraft(null)
    },
  })
  const editable = session.status === 'ended' || session.status === 'failed'
  const current = turn.revisions.at(-1)
  const issues = openIssues(turn)
  const audio = turn.audio
  const sourceLabel = (source: string) =>
    (t.sources as Readonly<Record<string, string>>)[source] ?? source
  const changed = draft !== null && draft.trim() !== '' && draft.trim() !== turn.text
  return (
    <article
      id={`turn-${String(turn.seq)}`}
      tabIndex={-1}
      aria-labelledby={`answer-${String(turn.seq)}`}
      data-testid="turn-candidate"
      data-flagged={issues.length > 0 || undefined}
      className={cn(
        'flex scroll-mt-6 flex-col gap-2 self-end rounded-2xl rounded-br-md bg-brand/10 px-4 py-3 ring-1 ring-brand/20 outline-none focus-visible:ring-2 focus-visible:ring-ring',
        draft === null ? 'max-w-[min(85%,52rem)]' : 'w-full max-w-[52rem]',
        issues.length > 0 && 'ring-2 ring-warning/60',
      )}
    >
      <header className="flex flex-wrap items-center justify-between gap-x-3 gap-y-1">
        <h3 id={`answer-${String(turn.seq)}`} className="text-xs font-semibold text-foreground/75">
          {t.answer(number)}
          <span className="font-normal text-muted-foreground"> · {clock(turn.elapsed_s)}</span>
        </h3>
        {current && <Badge variant="outline">{sourceLabel(current.source)}</Badge>}
      </header>
      {issues.length > 0 && (
        <ul
          data-testid="answer-issues"
          className="flex flex-col gap-1.5 rounded-lg border border-warning/40 bg-warning/10 px-3 py-2 text-sm"
        >
          {issues.map((issue) => (
            <li key={issue} className="flex items-start gap-2">
              <TriangleAlertIcon className="mt-0.5 size-4 shrink-0 text-warning" aria-hidden />
              <span>{t.issues[issue]}</span>
            </li>
          ))}
        </ul>
      )}
      {draft === null ? (
        <p data-testid="answer-text" className="leading-relaxed whitespace-pre-wrap">
          {turn.words.length > 0 ? (
            <Words
              words={turn.words}
              onListen={
                audio && player
                  ? (word) => {
                      player.playRange(
                        audio,
                        word.start_s - WORD_MARGIN_S,
                        word.end_s + WORD_MARGIN_S,
                      )
                    }
                  : undefined
              }
            />
          ) : (
            turn.text || <em>{t.noSpeech}</em>
          )}
        </p>
      ) : (
        <form
          className="flex flex-col gap-2"
          onSubmit={(event) => {
            event.preventDefault()
            if (changed) save.mutate(draft)
          }}
        >
          <label htmlFor={`edit-${String(turn.seq)}`} className="text-sm font-medium">
            {t.corrected} <RequiredMark />
          </label>
          <Textarea
            id={`edit-${String(turn.seq)}`}
            value={draft}
            required
            autoFocus
            aria-describedby={`edit-keys-${String(turn.seq)}`}
            className="min-h-28 bg-background"
            onChange={(event) => {
              setDraft(event.target.value)
            }}
            onKeyDown={(event) => {
              if (event.key === 'Escape') {
                event.preventDefault()
                setDraft(null)
              } else if (event.key === 'Enter' && (event.metaKey || event.ctrlKey)) {
                event.preventDefault()
                event.currentTarget.form?.requestSubmit()
              }
            }}
          />
          <p id={`edit-keys-${String(turn.seq)}`} className="text-xs text-muted-foreground">
            {t.keys}
          </p>
          <div className="flex flex-wrap items-center gap-2">
            <Button size="sm" disabled={save.isPending || !changed}>
              {save.isPending ? t.saving : t.save}
            </Button>
            <Button
              type="button"
              size="sm"
              variant="ghost"
              onClick={() => {
                setDraft(null)
              }}
            >
              {t.cancel}
            </Button>
            {audio && <TurnAudioButton src={audio} label={t.answer(number)} />}
          </div>
          {save.error && (
            <p role="alert" className="text-sm text-destructive">
              {save.error.message}
            </p>
          )}
        </form>
      )}
      {draft === null && (audio || editable) && (
        <div className="-mx-2 flex flex-wrap items-center gap-1">
          {audio && <TurnAudioButton src={audio} label={t.answer(number)} />}
          {editable && (
            <Button
              size="sm"
              variant="ghost"
              onClick={() => {
                setDraft(turn.text)
              }}
            >
              <PencilIcon data-icon="inline-start" />
              {t.correct}
            </Button>
          )}
        </div>
      )}
      {turn.revisions.length > 1 && (
        <details className="text-sm">
          <summary className="cursor-pointer font-medium">{t.history}</summary>
          <ol className="mt-2 flex flex-col gap-2">
            {turn.revisions
              .slice(0, -1)
              .toReversed()
              .map((revision) => (
                <li key={revision.number} className="rounded-lg border bg-background/60 px-3 py-2">
                  <p className="text-xs text-foreground/75">
                    v{revision.number} · {sourceLabel(revision.source)}
                  </p>
                  <p className="mt-1 whitespace-pre-wrap">{revision.text}</p>
                </li>
              ))}
          </ol>
        </details>
      )}
    </article>
  )
}
