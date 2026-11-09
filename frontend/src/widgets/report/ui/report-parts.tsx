import type { ReactNode } from 'react'
import { CheckIcon, CircleAlertIcon, InfoIcon, MinusIcon } from 'lucide-react'

import type { AboutView, CriterionView, CvCheckView, NoteView, QuoteView } from '@/entities/report'
import { useMessages } from '@/shared/i18n'
import { minutes, score } from '@/shared/lib/format'
import { useLanguage } from '@/shared/lib/preferences'
import { Badge } from '@/shared/ui/badge'
import { reportMessages } from './messages'

export function ReportSection({
  id,
  title,
  children,
}: {
  id: string
  title: string
  children: ReactNode
}) {
  return (
    <section id={id} aria-labelledby={`${id}-title`} className="scroll-mt-6 flex flex-col gap-4">
      <h2 id={`${id}-title`} className="font-heading text-2xl font-semibold tracking-tight">
        {title}
      </h2>
      {children}
    </section>
  )
}

export function Quotes({ quotes }: { quotes: QuoteView[] }) {
  const t = useMessages(reportMessages)
  return (
    <div className="flex flex-col gap-2">
      {quotes.map((quote, i) => (
        <blockquote
          key={i}
          className="border-l-2 border-brand/35 pl-3 text-sm text-muted-foreground"
        >
          “{quote.text}”{' '}
          {quote.answer !== null && (
            <a className="ml-1 text-brand-text underline" href={`#answer-${String(quote.turnSeq)}`}>
              {t.answer(quote.answer)}
            </a>
          )}
        </blockquote>
      ))}
    </div>
  )
}

export function Notes({ notes }: { notes: NoteView[] }) {
  const t = useMessages(reportMessages)
  if (!notes.length) return <p className="text-sm text-muted-foreground">{t.noNotes}</p>
  return (
    <div className="flex flex-col gap-3">
      {notes.map((note, i) => (
        <article
          key={i}
          className={`flex flex-col gap-3 rounded-xl border bg-card p-5 ${note.kind === 'technical_error' ? 'border-highlight/50' : ''}`}
        >
          {note.unit !== null && (
            <a
              href={`#question-${String(note.unit)}`}
              className="self-start text-xs font-semibold text-brand-text underline"
            >
              {t.question(note.unit)}
            </a>
          )}
          <p className="leading-relaxed whitespace-pre-wrap">{note.text}</p>
          <Quotes quotes={note.quotes} />
          {note.replacement && (
            <div className="rounded-lg border-l-4 border-highlight bg-muted p-4 text-sm text-foreground">
              <p className="mb-1 font-semibold">{t.correction}</p>
              <p className="whitespace-pre-wrap">{note.replacement}</p>
            </div>
          )}
        </article>
      ))}
    </div>
  )
}

export function Criteria({ criteria }: { criteria: CriterionView[] }) {
  const t = useMessages(reportMessages)
  const language = useLanguage()
  return (
    <div className="grid gap-4 sm:grid-cols-2">
      {criteria.map((item) => (
        <article key={item.id} className="flex flex-col gap-2 rounded-xl border bg-card p-4">
          <h3 className="flex items-start justify-between gap-3 text-sm font-semibold">
            <span>{item.label}</span>
            <span className="shrink-0 tabular-nums">
              {item.value === null
                ? t.statuses.not_assessable
                : `${score(item.value, language)} / 5`}
            </span>
          </h3>
          {item.value !== null && (
            <div
              role="meter"
              aria-valuemin={1}
              aria-valuemax={5}
              aria-valuenow={item.value}
              aria-label={item.label}
              className="h-1.5 overflow-hidden rounded-full bg-muted"
            >
              <div
                className="h-full rounded-full bg-brand"
                style={{ width: `${String((item.value / 5) * 100)}%` }}
              />
            </div>
          )}
          <p className="text-sm text-muted-foreground">{item.reason}</p>
          {item.unstable && (
            <Badge variant="outline" className="self-start">
              {t.unstable}
            </Badge>
          )}
          <Quotes quotes={item.quotes} />
        </article>
      ))}
    </div>
  )
}

export function Hero({
  view,
}: {
  view: {
    overall: number | null
    band: 'solid' | 'developing' | 'needs_work' | null
    assessed: number
    criteriaCount: number
    summary: NoteView | null
  }
}) {
  const t = useMessages(reportMessages)
  const language = useLanguage()
  return (
    <section
      id="overview"
      aria-label={t.overall}
      className="relative overflow-hidden rounded-2xl border bg-card p-6 sm:p-8"
    >
      <div
        aria-hidden="true"
        className="absolute inset-x-0 top-0 h-1"
        style={{ background: 'var(--brand-gradient)' }}
      />
      <div className="grid gap-6 sm:grid-cols-[12rem_1fr] sm:items-center">
        <div>
          <p className="text-sm text-muted-foreground">{t.overall}</p>
          <p className="my-2 font-heading text-5xl font-bold tabular-nums">
            {view.overall === null ? '—' : score(view.overall, language)}
            <span className="ml-2 text-lg font-normal text-muted-foreground">/ 5</span>
          </p>
          {view.band && <Badge variant="secondary">{t.bands[view.band]}</Badge>}
        </div>
        <div className="flex flex-col gap-3">
          <p className="text-lg leading-relaxed">
            {view.summary?.text ?? (view.overall === null ? t.unscored : t.noNotes)}
          </p>
          {view.summary && <Quotes quotes={view.summary.quotes} />}
          <p className="text-sm text-muted-foreground">
            {t.assessed(view.assessed, view.criteriaCount)}
          </p>
        </div>
      </div>
    </section>
  )
}

export function Checks({ checks }: { checks: CvCheckView[] }) {
  const t = useMessages(reportMessages)
  const icons = {
    review: CircleAlertIcon,
    info: InfoIcon,
    pass: CheckIcon,
    not_assessable: MinusIcon,
  }
  return (
    <ul className="divide-y rounded-xl border bg-card px-5">
      {checks.map((check) => {
        const Icon = icons[check.status]
        return (
          <li key={check.id} className="flex gap-3 py-4">
            <Icon aria-hidden="true" className="mt-0.5 size-4 shrink-0" />
            <div className="flex flex-col gap-2">
              <p className="text-xs font-semibold text-muted-foreground">
                {t.statuses[check.status]}
              </p>
              <p className="text-sm">{check.detail}</p>
              <Quotes quotes={check.quotes} />
            </div>
          </li>
        )
      })}
    </ul>
  )
}

export function TechnicalDetails({ about, unstable }: { about: AboutView; unstable: boolean }) {
  const t = useMessages(reportMessages)
  const rows = [
    [t.model, about.model],
    [t.prompt, about.prompt],
    [t.rubric, `${about.rubric} · ${about.rubricHash}`],
    [t.fingerprint, about.fingerprint],
    [t.dropped, about.dropped],
    [t.edited, about.editedAnswers],
    [t.processing, minutes(about.durationS)],
  ]
  return (
    <details id="technical" className="rounded-xl border p-5 text-sm">
      <summary className="cursor-pointer font-semibold">{t.technical}</summary>
      <dl className="mt-4 grid gap-3 sm:grid-cols-2">
        {rows.map(([label, value]) => (
          <div key={String(label)}>
            <dt className="text-xs text-muted-foreground">{label}</dt>
            <dd className="mt-1 break-words">{value}</dd>
          </div>
        ))}
      </dl>
      {unstable && <p className="mt-4">{t.unstableNote}</p>}
      <p className="mt-4 text-muted-foreground">{about.disclaimer}</p>
    </details>
  )
}
