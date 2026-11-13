import { useMutation } from '@tanstack/react-query'
import { PlusIcon, SparklesIcon, Trash2Icon } from 'lucide-react'

import { MAX_RESOURCES, OFFER_SOURCES, emptyResource, emptySlot } from '@/entities/preparation'
import type { DocumentSlot, DocumentsDraft, ResourceSlot } from '@/entities/preparation'
import { api } from '@/shared/api'
import type { ExecutionProfile } from '@/shared/api'
import { useMessages } from '@/shared/i18n'
import { Button } from '@/shared/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/shared/ui/card'
import { ChoiceCard } from '@/shared/ui/choice-card'
import { Input } from '@/shared/ui/input'
import { RadioGroup } from '@/shared/ui/radio-group'
import { RequiredMark } from '@/shared/ui/required-mark'
import { Textarea } from '@/shared/ui/textarea'
import { MAX_TITLE } from '../model/documents'
import { DocumentField } from './document-field'
import { documentsMessages } from './messages'

type Update = (update: (documents: DocumentsDraft) => DocumentsDraft) => void

function OfferSection({
  id,
  documents,
  language,
  execution,
  onChange,
}: {
  id: string
  documents: DocumentsDraft
  language: 'it' | 'en'
  execution: ExecutionProfile
  onChange: Update
}) {
  const t = useMessages(documentsMessages)
  const source = documents.offerSource
  const setOffer = (offer: DocumentSlot) => {
    onChange((d) => ({ ...d, offer }))
  }
  const draft = useMutation({
    mutationFn: () =>
      api.draftJobOffer({
        description: documents.description,
        language,
        execution_profile: execution,
      }),
    onSuccess: ({ text }) => {
      setOffer({ ...emptySlot('Job offer'), text, generated: true })
    },
  })
  const choose = (value: string) => {
    const next = OFFER_SOURCES.find((s) => s === value)
    if (!next) return
    // A drafted offer must not pass for a real one, and the other way round.
    onChange((d) =>
      next === 'none' || d.offer.generated === (next === 'describe')
        ? { ...d, offerSource: next }
        : { ...d, offerSource: next, offer: emptySlot('Job offer') },
    )
  }
  return (
    <Card>
      <CardHeader>
        <CardTitle role="heading" aria-level={2}>
          {t.offer.title}
        </CardTitle>
        <CardDescription>{t.offer.description}</CardDescription>
      </CardHeader>
      <CardContent className="flex flex-col gap-5">
        <RadioGroup
          aria-label={t.offer.source}
          value={source}
          onValueChange={choose}
          className="grid-cols-1 sm:grid-cols-3"
        >
          {OFFER_SOURCES.map((value) => (
            <ChoiceCard
              key={value}
              id={`${id}-source-${value}`}
              value={value}
              title={t.offer[value].title}
              description={t.offer[value].description}
            />
          ))}
        </RadioGroup>
        {source === 'describe' && (
          <div className="flex flex-col gap-2">
            <label htmlFor={`${id}-description`} className="text-sm font-medium">
              {t.offer.descriptionLabel}
            </label>
            <Textarea
              id={`${id}-description`}
              maxLength={3000}
              value={documents.description}
              onChange={(event) => {
                onChange((d) => ({ ...d, description: event.target.value }))
              }}
            />
            <Button
              type="button"
              variant="outline"
              className="self-start"
              disabled={documents.description.trim().length < 10 || draft.isPending}
              onClick={() => {
                draft.mutate()
              }}
            >
              <SparklesIcon data-icon="inline-start" />
              {draft.isPending
                ? t.offer.drafting
                : documents.offer.text
                  ? t.offer.redraft
                  : t.offer.draft}
            </Button>
            {draft.error && (
              <p role="alert" className="text-sm text-destructive">
                {draft.error.message}
              </p>
            )}
          </div>
        )}
        {(source === 'document' || (source === 'describe' && documents.offer.text)) && (
          <>
            {source === 'describe' && (
              <p className="text-sm text-muted-foreground">{t.offer.drafted}</p>
            )}
            <DocumentField
              id={`${id}-offer`}
              kind="job_offer"
              label={t.offer.text}
              required
              upload={source === 'document'}
              slot={documents.offer}
              onChange={(offer) => {
                setOffer({ ...offer, generated: source === 'describe' })
              }}
            />
          </>
        )}
      </CardContent>
    </Card>
  )
}

function ResourcesSection({
  id,
  resources,
  onChange,
}: {
  id: string
  resources: ResourceSlot[]
  onChange: Update
}) {
  const t = useMessages(documentsMessages)
  const update = (key: string, slot: DocumentSlot) => {
    onChange((d) => ({
      ...d,
      resources: d.resources.map((r) => (r.key === key ? { ...slot, key } : r)),
    }))
  }
  return (
    <Card>
      <CardHeader>
        <CardTitle role="heading" aria-level={2}>
          {t.resources.title}
        </CardTitle>
        <CardDescription>{t.resources.description}</CardDescription>
      </CardHeader>
      <CardContent className="flex flex-col gap-4">
        {resources.map((resource, index) => (
          <section
            key={resource.key}
            aria-labelledby={`${id}-${resource.key}-heading`}
            className="flex flex-col gap-3 rounded-lg border p-4"
            data-testid="resource-row"
          >
            <div className="flex items-center justify-between">
              <h3 id={`${id}-${resource.key}-heading`} className="text-sm font-medium">
                {t.resources.item(index + 1)}
              </h3>
              <Button
                type="button"
                variant="ghost"
                size="icon"
                aria-label={t.resources.remove(index + 1)}
                onClick={() => {
                  onChange((d) => ({
                    ...d,
                    resources: d.resources.filter((r) => r.key !== resource.key),
                  }))
                }}
              >
                <Trash2Icon className="size-4" />
              </Button>
            </div>
            <label
              htmlFor={`${id}-${resource.key}-title`}
              className="flex items-center gap-1 text-sm font-medium"
            >
              {t.resources.name} <RequiredMark />
            </label>
            <Input
              id={`${id}-${resource.key}-title`}
              required
              maxLength={MAX_TITLE}
              value={resource.title}
              onChange={(event) => {
                update(resource.key, { ...resource, title: event.target.value })
              }}
            />
            <DocumentField
              id={`${id}-${resource.key}`}
              kind="resource"
              label={t.resources.text}
              required
              slot={resource}
              onChange={(slot) => {
                update(resource.key, slot)
              }}
            />
          </section>
        ))}
        <Button
          type="button"
          variant="outline"
          className="self-start"
          disabled={resources.length >= MAX_RESOURCES}
          onClick={() => {
            onChange((d) => ({ ...d, resources: [...d.resources, emptyResource()] }))
          }}
        >
          <PlusIcon data-icon="inline-start" />
          {t.resources.add}
        </Button>
        {resources.length >= MAX_RESOURCES && (
          <p className="text-sm text-muted-foreground">{t.resources.limit(MAX_RESOURCES)}</p>
        )}
      </CardContent>
    </Card>
  )
}

/** The CV, the job offer and the resources of one interview, all editable. */
export function DocumentsEditor({
  id,
  documents,
  language,
  execution,
  onChange,
}: {
  id: string
  documents: DocumentsDraft
  language: 'it' | 'en'
  execution: ExecutionProfile
  onChange: Update
}) {
  const t = useMessages(documentsMessages)
  return (
    <div className="flex flex-col gap-6">
      {/* Wide windows put the CV beside the offer it is read against, at the same height. */}
      <div className="grid gap-6 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle role="heading" aria-level={2}>
              {t.cv.title}
            </CardTitle>
            <CardDescription>{t.cv.description}</CardDescription>
          </CardHeader>
          <CardContent>
            <DocumentField
              id={`${id}-cv`}
              kind="cv"
              label={t.cv.text}
              required
              slot={documents.cv}
              onChange={(cv) => {
                onChange((d) => ({ ...d, cv }))
              }}
            />
          </CardContent>
        </Card>
        <OfferSection
          id={id}
          documents={documents}
          language={language}
          execution={execution}
          onChange={onChange}
        />
      </div>
      <ResourcesSection id={id} resources={documents.resources} onChange={onChange} />
    </div>
  )
}
