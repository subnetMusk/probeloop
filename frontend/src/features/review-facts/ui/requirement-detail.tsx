import { TriangleAlertIcon } from 'lucide-react'

import type { Obligation, RequirementDetailView } from '@/shared/api'
import { defineMessages, useMessages } from '@/shared/i18n'
import { Button } from '@/shared/ui/button'

const OBLIGATIONS: Obligation[] = ['must', 'preferred', 'unclear']

const messages = defineMessages({
  en: {
    obligation: 'How binding',
    values: { must: 'Required', preferred: 'Preferred', unclear: 'Unclear' },
    cue: (cue: string) => `from “${cue}”`,
    byUser: 'set by you',
    anyOf: (members: string) => `Any of: ${members}`,
    similar: 'or similar',
    equivalents: (routes: string) => `Or: ${routes}`,
    threshold: {
      years: (minimum: string, subject: string) =>
        `At least ${minimum} years${subject ? ` of ${subject}` : ''}`,
      language_level: (minimum: string, subject: string) =>
        `Level ${minimum} or higher${subject ? ` in ${subject}` : ''}`,
      degree: (minimum: string, subject: string) =>
        `Degree: ${minimum}${subject ? ` (${subject})` : ''}`,
    },
    implicit: 'Not written in the offer: implied by it.',
    disputed: (readings: string) => `The sources disagree (${readings}). Choose the right one.`,
    sources: { user: 'you', cue: 'the offer', jev: 'Jev', model: 'analysis model' },
  },
  it: {
    obligation: 'Quanto è vincolante',
    values: { must: 'Obbligatorio', preferred: 'Preferito', unclear: 'Non chiaro' },
    cue: (cue: string) => `da «${cue}»`,
    byUser: 'scelto da te',
    anyOf: (members: string) => `Basta uno tra: ${members}`,
    similar: 'o simili',
    equivalents: (routes: string) => `Oppure: ${routes}`,
    threshold: {
      years: (minimum: string, subject: string) =>
        `Almeno ${minimum} anni${subject ? ` di ${subject}` : ''}`,
      language_level: (minimum: string, subject: string) =>
        `Livello ${minimum} o superiore${subject ? ` in ${subject}` : ''}`,
      degree: (minimum: string, subject: string) =>
        `Titolo: ${minimum}${subject ? ` (${subject})` : ''}`,
    },
    implicit: 'Non scritto nell’offerta: lo si deduce dal testo.',
    disputed: (readings: string) => `Le fonti non concordano (${readings}). Scegli tu.`,
    sources: { user: 'tu', cue: 'l’offerta', jev: 'Jev', model: 'modello di analisi' },
  },
})

type Messages = (typeof messages)['en']

function thresholdText(t: Messages, threshold: NonNullable<RequirementDetailView['threshold']>) {
  const format = t.threshold[threshold.kind as keyof Messages['threshold']]
  return format(threshold.minimum, threshold.subject)
}

/**
 * The structure of a job requirement during the review: how binding it is and why, what
 * satisfies it, and a choice that overrides every reading when the user knows better.
 */
export function RequirementDetail({
  id,
  detail,
  onObligation,
}: {
  id: string
  detail: RequirementDetailView
  onObligation: (obligation: Obligation) => void
}) {
  const t = useMessages(messages)
  const facts = [
    detail.any_of.length > 0 &&
      t.anyOf(
        detail.any_of.map((a) => (a.open ? `${a.value} (${t.similar})` : a.value)).join(', '),
      ),
    detail.equivalents.length > 0 &&
      t.equivalents(detail.equivalents.map((e) => e.value).join(', ')),
    detail.threshold && thresholdText(t, detail.threshold),
    detail.implicit && t.implicit,
  ].filter((part): part is string => typeof part === 'string')
  const readings = detail.readings
    .map((r) => `${t.sources[r.source]}: ${t.values[r.obligation].toLowerCase()}`)
    .join(', ')
  return (
    <div className="flex flex-col gap-2" data-testid="requirement-detail">
      <div className="flex flex-wrap items-center gap-2">
        <span id={`obligation-${id}`} className="text-xs font-medium text-muted-foreground">
          {t.obligation}
        </span>
        <div role="group" aria-labelledby={`obligation-${id}`} className="flex flex-wrap gap-1">
          {OBLIGATIONS.map((value) => (
            <Button
              key={value}
              type="button"
              size="sm"
              variant={detail.obligation === value ? 'default' : 'outline'}
              aria-pressed={detail.obligation === value}
              className="h-7 px-2 text-xs"
              onClick={() => {
                if (detail.obligation !== value) onObligation(value)
              }}
            >
              {t.values[value]}
            </Button>
          ))}
        </div>
        {detail.readings.some((r) => r.source === 'user') ? (
          <span className="text-xs text-muted-foreground">{t.byUser}</span>
        ) : (
          detail.cue && <span className="text-xs text-muted-foreground">{t.cue(detail.cue)}</span>
        )}
      </div>
      {facts.length > 0 && (
        <ul className="list-disc pl-5 text-xs text-muted-foreground">
          {facts.map((fact) => (
            <li key={fact}>{fact}</li>
          ))}
        </ul>
      )}
      {detail.disputed && (
        <p className="flex items-start gap-1.5 text-xs" role="note">
          <TriangleAlertIcon className="mt-px size-3.5 shrink-0 text-warning" aria-hidden="true" />
          {t.disputed(readings)}
        </p>
      )}
    </div>
  )
}
