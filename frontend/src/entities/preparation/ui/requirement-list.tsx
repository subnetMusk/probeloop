import { CheckIcon, CircleIcon, XIcon } from 'lucide-react'

import { defineMessages, useMessages } from '@/shared/i18n'

export interface Requirement {
  id: string
  text: string
  kind: string
  status: string
  supporting: string[]
}

const messages = defineMessages({
  en: {
    met: 'Shown',
    partial: 'Partly shown',
    not_shown: 'Not shown',
    niceToHave: 'nice to have',
    supporting: 'From your documents:',
    none: 'No requirement was found in the job offer.',
  },
  it: {
    met: 'Dimostrato',
    partial: 'In parte',
    not_shown: 'Non dimostrato',
    niceToHave: 'gradito',
    supporting: 'Dai tuoi documenti:',
    none: 'Nell’offerta non è stato trovato alcun requisito.',
  },
})

const ORDER: Record<string, number> = { not_shown: 0, partial: 1, met: 2 }

function Status({ status }: { status: string }) {
  const t = useMessages(messages)
  if (status === 'met')
    return (
      <span className="flex shrink-0 items-center gap-1.5 text-xs font-medium">
        <CheckIcon className="size-4 text-success" aria-hidden="true" />
        {t.met}
      </span>
    )
  if (status === 'partial')
    return (
      <span className="flex shrink-0 items-center gap-1.5 text-xs font-medium">
        <CircleIcon className="size-4 text-warning" aria-hidden="true" />
        {t.partial}
      </span>
    )
  return (
    <span className="flex shrink-0 items-center gap-1.5 text-xs font-medium">
      <XIcon className="size-4 text-destructive" aria-hidden="true" />
      {t.not_shown}
    </span>
  )
}

/** The requirements of a job offer and how the candidate's documents cover them. */
export function RequirementList({ requirements }: { requirements: readonly Requirement[] }) {
  const t = useMessages(messages)
  if (requirements.length === 0) return <p className="text-muted-foreground">{t.none}</p>
  const sorted = [...requirements].sort((a, b) => (ORDER[a.status] ?? 0) - (ORDER[b.status] ?? 0))
  return (
    <ul className="flex flex-col" data-testid="requirements">
      {sorted.map((row) => (
        <li key={row.id} className="flex flex-col gap-1 border-b py-3 last:border-0">
          <div className="flex items-start justify-between gap-3">
            <p>
              {row.text}
              {row.kind === 'nice_to_have' && (
                <span className="text-muted-foreground"> ({t.niceToHave})</span>
              )}
            </p>
            <Status status={row.status} />
          </div>
          {row.supporting.length > 0 && (
            <p className="text-sm text-muted-foreground">
              {t.supporting} {row.supporting.join('; ')}
            </p>
          )}
        </li>
      ))}
    </ul>
  )
}
