import { useMutation } from '@tanstack/react-query'
import { CheckIcon, CircleDashedIcon, PencilIcon, XIcon } from 'lucide-react'
import { useState } from 'react'
import type { ReactNode } from 'react'
import { cn } from 'cn'

import { RequirementList } from '@/entities/preparation'
import { api } from '@/shared/api'
import type { AddFactIn, FactView, PreparationView } from '@/shared/api'
import { useMessages } from '@/shared/i18n'
import { Badge } from '@/shared/ui/badge'
import { Button } from '@/shared/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/shared/ui/card'
import { Input } from '@/shared/ui/input'
import { RequiredMark } from '@/shared/ui/required-mark'
import { Textarea } from '@/shared/ui/textarea'
import { summarise } from '../model/summary'
import type { RequirementRow } from '../model/summary'
import { reviewMessages } from './messages'
import { RequirementDetail } from './requirement-detail'

type Messages = (typeof reviewMessages)['en']
type Review = 'confirmed' | 'excluded' | 'corrected' | 'pending'
type Act = (task: () => Promise<PreparationView>) => void

const kindLabel = (t: Messages, kind: string) =>
  kind in t.kinds ? t.kinds[kind as keyof Messages['kinds']] : kind
const originLabel = (t: Messages, origin: string) =>
  origin in t.fact.origin ? t.fact.origin[origin as keyof Messages['fact']['origin']] : origin

function ReviewIcon({ review }: { review: string }) {
  const t = useMessages(reviewMessages)
  if (review === 'excluded')
    return <XIcon className="size-5 shrink-0 text-destructive" aria-label={t.fact.excluded} />
  if (review === 'confirmed' || review === 'corrected')
    return <CheckIcon className="size-5 shrink-0 text-success" aria-label={t.fact.confirmed} />
  return (
    <CircleDashedIcon
      className="size-5 shrink-0 text-muted-foreground"
      aria-label={t.fact.pending}
    />
  )
}

function FactItem({
  fact,
  preparationId,
  act,
  detailed = false,
}: {
  fact: FactView
  preparationId: string
  act: Act
  detailed?: boolean
}) {
  const t = useMessages(reviewMessages)
  const [draft, setDraft] = useState<string | null>(null)
  const review = (value: Review, corrected?: string) => {
    act(() => api.reviewFact(preparationId, fact.id, { review: value, corrected }))
  }
  const confirmed = fact.review === 'confirmed' || fact.review === 'corrected'
  const excluded = fact.review === 'excluded'
  return (
    <li className="flex gap-3 border-b py-3 last:border-0" data-testid="context-fact">
      <ReviewIcon review={fact.review} />
      <div className="flex min-w-0 flex-1 flex-col gap-1.5">
        <p className={cn(excluded && 'text-muted-foreground line-through')}>{fact.text}</p>
        <p className="text-xs text-muted-foreground">
          {kindLabel(t, fact.kind)} · {originLabel(t, fact.origin)}
        </p>
        {fact.requirement && (
          <RequirementDetail
            id={fact.id}
            detail={fact.requirement}
            onObligation={(obligation) => {
              act(() => api.setObligation(preparationId, fact.id, obligation))
            }}
          />
        )}
        {detailed && fact.quote && (
          <blockquote className="rounded-lg bg-muted/70 px-3 py-2 text-sm text-muted-foreground">
            <span className="sr-only">{t.fact.quote}: </span>“{fact.quote}”
          </blockquote>
        )}
        {draft !== null ? (
          <form
            className="flex flex-col gap-2"
            onSubmit={(event) => {
              event.preventDefault()
              if (!draft.trim()) return
              review('corrected', draft)
              setDraft(null)
            }}
          >
            <label htmlFor={`correct-${fact.id}`} className="text-sm font-medium">
              {t.fact.corrected}
            </label>
            <Textarea
              id={`correct-${fact.id}`}
              maxLength={400}
              value={draft}
              onChange={(event) => {
                setDraft(event.target.value)
              }}
            />
            <div className="flex gap-2">
              <Button type="submit" size="sm" disabled={!draft.trim()}>
                {t.fact.save}
              </Button>
              <Button
                type="button"
                size="sm"
                variant="ghost"
                onClick={() => {
                  setDraft(null)
                }}
              >
                {t.fact.cancel}
              </Button>
            </div>
          </form>
        ) : (
          <div className="flex flex-wrap gap-2">
            <Button
              type="button"
              size="sm"
              variant="outline"
              aria-pressed={confirmed}
              className={cn(confirmed && 'border-success')}
              onClick={() => {
                review(confirmed ? 'pending' : 'confirmed')
              }}
            >
              <CheckIcon className="text-success" data-icon="inline-start" />
              {t.fact.confirm}
            </Button>
            <Button
              type="button"
              size="sm"
              variant="outline"
              aria-pressed={excluded}
              className={cn(excluded && 'border-destructive')}
              onClick={() => {
                review(excluded ? 'pending' : 'excluded')
              }}
            >
              <XIcon className="text-destructive" data-icon="inline-start" />
              {t.fact.exclude}
            </Button>
            <Button
              type="button"
              size="sm"
              variant="ghost"
              onClick={() => {
                setDraft(fact.text)
              }}
            >
              <PencilIcon data-icon="inline-start" />
              {t.fact.correct}
            </Button>
          </div>
        )}
      </div>
    </li>
  )
}

function Requirements({ rows }: { rows: RequirementRow[] }) {
  const t = useMessages(reviewMessages)
  return (
    <Card>
      <CardHeader>
        <CardTitle role="heading" aria-level={2}>
          {t.requirements.title}
        </CardTitle>
        <CardDescription>{t.requirements.hint}</CardDescription>
      </CardHeader>
      <CardContent>
        <RequirementList requirements={rows} />
      </CardContent>
    </Card>
  )
}

function Area({ preparation, act }: { preparation: PreparationView; act: Act }) {
  const t = useMessages(reviewMessages)
  const [area, setArea] = useState(preparation.area?.area ?? '')
  const [seniority, setSeniority] = useState(preparation.area?.seniority ?? '')
  return (
    <Card>
      <CardHeader>
        <CardTitle role="heading" aria-level={2} className="flex items-center gap-1">
          {t.area.title} <RequiredMark />
        </CardTitle>
        <CardDescription>{t.area.hint}</CardDescription>
      </CardHeader>
      <CardContent>
        <form
          className="flex flex-col gap-3"
          onSubmit={(event) => {
            event.preventDefault()
            if (!area.trim()) return
            act(() => api.setArea(preparation.id, { area, seniority }))
          }}
        >
          {preparation.area?.rationale && <p className="text-sm">{preparation.area.rationale}</p>}
          <div className="grid gap-3 sm:grid-cols-[2fr_1fr]">
            <div className="flex flex-col gap-2">
              <label htmlFor="area" className="flex items-center gap-1 text-sm font-medium">
                {t.area.area} <RequiredMark />
              </label>
              <Input
                id="area"
                required
                maxLength={120}
                value={area}
                onChange={(event) => {
                  setArea(event.target.value)
                }}
              />
            </div>
            <div className="flex flex-col gap-2">
              <label htmlFor="seniority" className="text-sm font-medium">
                {t.area.seniority}
              </label>
              <Input
                id="seniority"
                maxLength={40}
                value={seniority}
                onChange={(event) => {
                  setSeniority(event.target.value)
                }}
              />
            </div>
          </div>
          <div className="flex items-center gap-3">
            <Button type="submit" variant="outline" disabled={!area.trim()}>
              {preparation.area?.confirmed ? t.area.save : t.area.confirm}
            </Button>
            {preparation.area?.confirmed && (
              <span className="flex items-center gap-1 text-sm text-success">
                <CheckIcon className="size-4" aria-hidden="true" />
                {t.area.confirmed}
              </span>
            )}
          </div>
        </form>
      </CardContent>
    </Card>
  )
}

function AddFact({ preparationId, act }: { preparationId: string; act: Act }) {
  const t = useMessages(reviewMessages)
  const [subject, setSubject] = useState<AddFactIn['subject']>('candidate')
  const [statement, setStatement] = useState('')
  return (
    <form
      className="flex flex-col gap-3 pt-3"
      onSubmit={(event) => {
        event.preventDefault()
        if (!statement.trim()) return
        const kind = subject === 'candidate' ? 'other' : 'requirement'
        act(() => api.addFact(preparationId, { subject, kind, statement }))
        setStatement('')
      }}
    >
      <fieldset className="flex flex-wrap items-center gap-3 text-sm">
        <legend className="sr-only">{t.add.subject}</legend>
        {(['candidate', 'job'] as const).map((value) => (
          <label key={value} className="flex items-center gap-1.5">
            <input
              type="radio"
              name="fact-subject"
              checked={subject === value}
              onChange={() => {
                setSubject(value)
              }}
            />
            {t.add[value]}
          </label>
        ))}
      </fieldset>
      <label htmlFor="new-fact" className="text-sm font-medium">
        {t.add.statement}
      </label>
      <Textarea
        id="new-fact"
        maxLength={400}
        value={statement}
        onChange={(event) => {
          setStatement(event.target.value)
        }}
      />
      <Button type="submit" variant="outline" className="self-start" disabled={!statement.trim()}>
        {t.add.submit}
      </Button>
    </form>
  )
}

function Disclosure({ title, children }: { title: string; children: ReactNode }) {
  return (
    <details className="group rounded-xl ring-1 ring-foreground/10">
      <summary className="cursor-pointer list-none px-4 py-3 font-heading font-semibold marker:hidden">
        <span className="mr-2 inline-block transition-transform group-open:rotate-90">›</span>
        {title}
      </summary>
      <div className="px-4 pb-4">{children}</div>
    </details>
  )
}

/**
 * The review of an analysed preparation. Doubtful facts are open; everything else is one click
 * away. Changing an approved review reopens it first, so that it is approved again.
 */
export function FactReview({
  preparation,
  onChange,
  onReopened,
}: {
  preparation: PreparationView
  onChange: (view: PreparationView) => void
  onReopened: () => void
}) {
  const t = useMessages(reviewMessages)
  const update = useMutation({
    mutationFn: async (task: () => Promise<PreparationView>) => {
      if (preparation.status === 'approved') {
        await api.reopen(preparation.id)
        onReopened()
      }
      return task()
    },
    onSuccess: onChange,
  })
  const act: Act = (task) => {
    update.mutate(task)
  }
  const summary = summarise(preparation)
  const warnings = preparation.documents.filter((d) => d.warnings.length > 0)
  return (
    <div className="flex flex-col gap-6" data-testid="context-review">
      <div className="flex flex-col gap-1 text-sm">
        <p>{t.counts(summary.counts.declared, summary.counts.total)}</p>
        <p className="text-muted-foreground">{t.declaredNote}</p>
        {preparation.job_mode === 'generated' && (
          <Badge variant="secondary" className="mt-2 self-start">
            {t.generated}
          </Badge>
        )}
      </div>
      {warnings.map((document) => (
        <div key={document.id} role="note" className="rounded-lg border border-warning/60 p-4">
          <h3 className="font-medium">{t.warnings(document.title)}</h3>
          {document.warnings.map((warning) => (
            <p key={warning} className="text-sm">
              {warning}
            </p>
          ))}
        </div>
      ))}
      <fieldset disabled={update.isPending} className="flex min-w-0 flex-col gap-6">
        {preparation.job_mode === 'none' && !preparation.role_profile && (
          <Area preparation={preparation} act={act} />
        )}
        <Card>
          <CardHeader>
            <CardTitle role="heading" aria-level={2} className="flex items-center gap-3">
              {t.doubtful.title}
              {summary.doubtful.length > 0 && (
                <Badge variant={summary.open ? 'secondary' : 'outline'}>
                  {t.doubtful.open(summary.open)}
                </Badge>
              )}
            </CardTitle>
            <CardDescription>
              {summary.doubtful.length ? t.doubtful.hint : t.doubtful.none}
            </CardDescription>
          </CardHeader>
          {summary.doubtful.length > 0 && (
            <CardContent>
              <ul data-testid="doubtful-facts">
                {summary.doubtful.map((fact) => (
                  <FactItem
                    key={fact.id}
                    fact={fact}
                    preparationId={preparation.id}
                    act={act}
                    detailed
                  />
                ))}
              </ul>
            </CardContent>
          )}
        </Card>
        {preparation.job_mode !== 'none' && <Requirements rows={summary.requirements} />}
        <Disclosure title={t.all.title(preparation.facts.length)}>
          {(['candidate', 'job'] as const).map((subject) => {
            const facts = preparation.facts.filter((f) => f.subject === subject)
            return (
              <section key={subject} aria-labelledby={`facts-${subject}`} className="pt-2">
                <h3 id={`facts-${subject}`} className="text-sm font-medium text-muted-foreground">
                  {t.all[subject]}
                </h3>
                {facts.length === 0 ? (
                  <p className="py-2 text-sm text-muted-foreground">{t.all.empty}</p>
                ) : (
                  <ul>
                    {facts.map((fact) => (
                      <FactItem
                        key={fact.id}
                        fact={fact}
                        preparationId={preparation.id}
                        act={act}
                      />
                    ))}
                  </ul>
                )}
              </section>
            )
          })}
        </Disclosure>
        <Disclosure title={t.add.title}>
          <AddFact preparationId={preparation.id} act={act} />
        </Disclosure>
      </fieldset>
      {update.error && (
        <p role="alert" className="text-destructive">
          {update.error.message}
        </p>
      )}
    </div>
  )
}
