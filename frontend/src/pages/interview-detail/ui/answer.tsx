import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { PencilIcon, TriangleAlertIcon } from 'lucide-react'

import { api } from '@/shared/api'
import type { SessionView, TurnView, WordView } from '@/shared/api'
import { useMessages } from '@/shared/i18n'
import { Badge } from '@/shared/ui/badge'
import { Button } from '@/shared/ui/button'
import { RequiredMark } from '@/shared/ui/required-mark'
import { Textarea } from '@/shared/ui/textarea'
import { openIssues } from '../model/review'
import { transcriptMessages } from './messages'

export function Words({ words }: { words: WordView[] }) {
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
              className="rounded-sm bg-amber-100 px-0.5 text-inherit underline decoration-amber-600 decoration-dotted dark:bg-amber-500/20"
            >
              {word.text}
            </mark>
          ) : (
            word.text
          )}
        </span>
      ))}
    </>
  )
}

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
  const sourceLabel = (source: string) =>
    (t.sources as Readonly<Record<string, string>>)[source] ?? source
  return (
    <div
      id={`turn-${String(turn.seq)}`}
      className="scroll-mt-6 rounded-xl bg-muted p-4"
      data-testid="turn-candidate"
    >
      <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
        <h3 className="text-xs font-semibold text-foreground/75">{t.answer(number)}</h3>
        {current && <Badge variant="outline">{sourceLabel(current.source)}</Badge>}
      </div>
      {issues.length > 0 && (
        <ul
          data-testid="answer-issues"
          className="mb-3 flex flex-col gap-1.5 rounded-lg border border-warning/40 bg-warning/10 px-3 py-2 text-sm"
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
            <Words words={turn.words} />
          ) : (
            turn.text || <em>{t.noSpeech}</em>
          )}
        </p>
      ) : (
        <form
          className="flex flex-col gap-3"
          onSubmit={(event) => {
            event.preventDefault()
            if (draft.trim() && draft.trim() !== turn.text) save.mutate(draft)
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
            onChange={(event) => {
              setDraft(event.target.value)
            }}
          />
          <div className="flex gap-2">
            <Button
              size="sm"
              disabled={save.isPending || !draft.trim() || draft.trim() === turn.text}
            >
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
          </div>
          {save.error && (
            <p role="alert" className="text-sm text-destructive">
              {save.error.message}
            </p>
          )}
        </form>
      )}
      {turn.audio && (
        <audio
          aria-label={t.answer(number)}
          controls
          preload="none"
          src={turn.audio}
          className="mt-3 h-9 w-full max-w-sm"
        />
      )}
      {editable && draft === null && (
        <Button
          size="sm"
          variant="ghost"
          className="mt-2"
          onClick={() => {
            setDraft(turn.text)
          }}
        >
          <PencilIcon data-icon="inline-start" />
          {t.correct}
        </Button>
      )}
      {turn.revisions.length > 1 && (
        <details className="mt-3 text-sm">
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
    </div>
  )
}
