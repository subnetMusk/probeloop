import { useIsMutating, useMutation, useQuery } from '@tanstack/react-query'
import { useNavigate, useSearch } from '@tanstack/react-router'
import { useState } from 'react'

import { MAX_PROFILE_NAME, emptyDocuments } from '@/entities/preparation'
import type { DocumentsDraft } from '@/entities/preparation'
import { profilesQuery } from '@/entities/profile'
import {
  DocumentsEditor,
  UPLOAD_KEY,
  documentsMessages,
  prepareDocuments,
  problemsOf,
  profileBody,
  storeDocuments,
  useProblemText,
} from '@/features/edit-documents'
import { ProfileSummary } from '@/features/select-profile'
import { api } from '@/shared/api'
import type { ProfileView } from '@/shared/api'
import { useMessages } from '@/shared/i18n'
import { useLanguage } from '@/shared/lib/preferences'
import { Button } from '@/shared/ui/button'
import { ChoiceCard } from '@/shared/ui/choice-card'
import { Input } from '@/shared/ui/input'
import { Page, PageHeader } from '@/shared/ui/page-header'
import { RadioGroup } from '@/shared/ui/radio-group'
import { RequiredMark } from '@/shared/ui/required-mark'
import { newCvCheckMessages } from './messages'

const ONE_OFF = 'documents'

/** The documents of a saved profile, analysed as they are. */
function prepareProfile(profile: ProfileView, language: 'it' | 'en', execution: string) {
  return api.prepare({
    language,
    job_mode: profile.job_mode,
    cv_id: profile.cv?.id ?? null,
    job_offer_id: profile.job_offer?.id ?? null,
    resources: profile.resources.map((r) => ({ title: r.title, document_id: r.id })),
    profile_id: profile.id,
    execution_profile: execution,
  })
}

/**
 * Start a CV check from a saved profile or from documents added here. The analysis then
 * continues on the review page, whose address holds the preparation.
 */
export function NewCvCheckPage() {
  const t = useMessages(newCvCheckMessages)
  const d = useMessages(documentsMessages)
  const language = useLanguage()
  const navigate = useNavigate()
  const describe = useProblemText()
  const search = useSearch({ from: '/cv-checks/new/' })
  const profiles = useQuery(profilesQuery)
  const execution = useQuery({ queryKey: ['execution-profile'], queryFn: api.executionProfile })
  const uploads = useIsMutating({ mutationKey: UPLOAD_KEY })
  const [source, setSource] = useState<string>(search.profile ?? '')
  const [documents, setDocuments] = useState<DocumentsDraft>(emptyDocuments)
  const [name, setName] = useState('')
  const profile = profiles.data?.find((p) => p.id === source)
  const start = useMutation({
    mutationFn: async () => {
      const plan = execution.data?.profile ?? 'local'
      if (profile) return prepareProfile(profile, language, plan)
      const stored = await storeDocuments(documents)
      setDocuments(stored)
      const saved = name.trim() ? await api.saveProfile(profileBody(name, stored)) : null
      return prepareDocuments(stored, { language, execution: plan, profileId: saved?.id ?? null })
    },
    onSuccess: (preparation) => {
      void navigate({
        to: '/cv-checks/new/$preparationId',
        params: { preparationId: preparation.id },
      })
    },
  })
  const problems = source === ONE_OFF ? problemsOf(documents) : []
  const hint =
    source === '' || (source !== ONE_OFF && !profile?.cv)
      ? t.missing.source
      : uploads > 0
        ? t.missing.uploading
        : problems.length
          ? `${d.problems.intro} ${problems.map(describe).join('; ')}.`
          : undefined
  return (
    <Page>
      <PageHeader eyebrow={t.eyebrow} title={t.title} description={t.description} />
      <fieldset>
        <legend className="mb-3 flex items-center gap-1 font-heading text-base font-semibold">
          {t.source} <RequiredMark />
        </legend>
        <RadioGroup aria-required value={source} onValueChange={setSource} className="gap-6">
          <section aria-labelledby="cv-check-saved" className="flex flex-col gap-2">
            <h3 id="cv-check-saved" className="text-sm font-medium text-muted-foreground">
              {t.saved}
            </h3>
            {profiles.isPending && <p className="text-sm text-muted-foreground">{t.loading}</p>}
            {profiles.error && (
              <p role="alert" className="text-sm text-destructive">
                {profiles.error.message}
              </p>
            )}
            <div className="grid gap-2 sm:grid-cols-2">
              {profiles.data?.map((p) => (
                <ChoiceCard
                  key={p.id}
                  id={`cv-check-profile-${p.id}`}
                  value={p.id}
                  title={p.name}
                  disabled={!p.cv}
                  description={p.cv ? <ProfileSummary profile={p} /> : t.noCv}
                />
              ))}
            </div>
          </section>
          <div className="grid gap-2 sm:grid-cols-2">
            <ChoiceCard
              id="cv-check-documents"
              value={ONE_OFF}
              title={t.oneOff.title}
              description={t.oneOff.description}
            />
          </div>
        </RadioGroup>
      </fieldset>
      {source === ONE_OFF && (
        <>
          <DocumentsEditor
            id="cv-check"
            documents={documents}
            language={language}
            execution={execution.data?.profile ?? 'local'}
            onChange={(update) => {
              setDocuments((current) => update(current))
            }}
          />
          <div className="flex max-w-md flex-col gap-2">
            <label htmlFor="cv-check-profile-name" className="text-sm font-medium">
              {t.saveAs}
            </label>
            <Input
              id="cv-check-profile-name"
              maxLength={MAX_PROFILE_NAME}
              aria-describedby="cv-check-profile-name-hint"
              value={name}
              onChange={(event) => {
                setName(event.target.value)
              }}
            />
            <p id="cv-check-profile-name-hint" className="text-sm text-muted-foreground">
              {t.saveAsHint}
            </p>
          </div>
        </>
      )}
      <div className="sticky bottom-0 z-10 -mx-6 flex flex-wrap items-center justify-between gap-3 border-t bg-background/95 px-6 py-4 backdrop-blur">
        <p className="text-sm text-muted-foreground" aria-live="polite">
          {hint}
        </p>
        <Button
          type="button"
          disabled={start.isPending || hint !== undefined || execution.data === undefined}
          onClick={() => {
            start.mutate()
          }}
        >
          {start.isPending ? t.analysing : t.analyse}
        </Button>
        {start.error && (
          <p role="alert" className="w-full text-sm text-destructive">
            {start.error.message}
          </p>
        )}
      </div>
    </Page>
  )
}
