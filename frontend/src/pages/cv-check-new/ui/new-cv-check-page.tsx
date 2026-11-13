import { useIsMutating, useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useNavigate, useSearch } from '@tanstack/react-router'
import { Loader2Icon } from 'lucide-react'
import { useEffect, useState } from 'react'

import { forgetCvCheckPreparation, rememberCvCheckPreparation } from '@/entities/cv-check'
import { MAX_PROFILE_NAME, emptyDocuments } from '@/entities/preparation'
import type { DocumentsDraft, ProfileChoice } from '@/entities/preparation'
import { profilesQuery } from '@/entities/profile'
import {
  DocumentsEditor,
  SaveProfileDialog,
  UPLOAD_KEY,
  commitProfileDocuments,
  documentsMessages,
  loadPreparationDocuments,
  loadProfileDocuments,
  prepareDocuments,
  problemsOf,
  storeDocuments,
  useProblemText,
} from '@/features/edit-documents'
import type { SaveChoice } from '@/features/edit-documents'
import { ProfileSummary } from '@/features/select-profile'
import { api } from '@/shared/api'
import type { PreparationView, ProfileView } from '@/shared/api'
import { useMessages } from '@/shared/i18n'
import { useLanguage } from '@/shared/lib/preferences'
import { Alert, AlertDescription } from '@/shared/ui/alert'
import { Button } from '@/shared/ui/button'
import { ChoiceCard } from '@/shared/ui/choice-card'
import { Input } from '@/shared/ui/input'
import { Page, PageHeader } from '@/shared/ui/page-header'
import { RadioGroup } from '@/shared/ui/radio-group'
import { RequiredMark } from '@/shared/ui/required-mark'
import { UnfinishedCvChecksNotice } from '@/widgets/cv-check-list'
import { newCvCheckMessages } from './messages'

const ONE_OFF = 'documents'

/**
 * The documents to edit: those of the preparation the user came back from, else those of the
 * chosen saved profile, loaded once per choice so that edits are kept.
 */
function useSourceDocuments(
  from: PreparationView | undefined,
  profile: ProfileView | undefined,
  documents: DocumentsDraft,
  setDocuments: (documents: DocumentsDraft) => void,
) {
  const wanted = from ? null : profile && documents.loadedFrom !== profile.id ? profile : null
  const load = useQuery({
    queryKey: ['profile-documents', wanted?.id, wanted?.updated_at],
    queryFn: () => loadProfileDocuments(wanted as ProfileView),
    enabled: wanted !== null,
    staleTime: Infinity,
  })
  const back = useQuery({
    queryKey: ['preparation-documents', from?.id],
    queryFn: () => loadPreparationDocuments(from as PreparationView),
    enabled: from !== undefined,
    staleTime: Infinity,
  })
  useEffect(() => {
    if (load.data && load.data.loadedFrom === wanted?.id) setDocuments(load.data)
  }, [load.data, wanted?.id, setDocuments])
  useEffect(() => {
    if (back.data) setDocuments(back.data)
  }, [back.data, setDocuments])
  return {
    loading: (wanted !== null && load.isPending) || (from !== undefined && back.isPending),
    error: load.error ?? back.error,
  }
}

/**
 * Start a CV check from a saved profile, whose documents can be corrected here, or from
 * documents added here. The analysis then continues on the review page, whose address holds the
 * preparation; coming back from it (`from`) refills the form with that preparation's documents.
 */
export function NewCvCheckPage() {
  const t = useMessages(newCvCheckMessages)
  const d = useMessages(documentsMessages)
  const language = useLanguage()
  const navigate = useNavigate()
  const client = useQueryClient()
  const describe = useProblemText()
  const search = useSearch({ from: '/cv-checks/new/' })
  const profiles = useQuery(profilesQuery)
  const execution = useQuery({ queryKey: ['execution-profile'], queryFn: api.executionProfile })
  const previous = useQuery({
    queryKey: ['preparation', search.from],
    queryFn: () => api.preparation(search.from ?? ''),
    enabled: search.from !== undefined,
  })
  const uploads = useIsMutating({ mutationKey: UPLOAD_KEY })
  // The user's choice; before one, the check gone back from, else the profile in the address.
  const [picked, setPicked] = useState<string | null>(null)
  const [documents, setDocuments] = useState<DocumentsDraft>(emptyDocuments)
  const [name, setName] = useState('')
  const [asking, setAsking] = useState(false)
  const from = previous.data
  // Coming back, the check's profile is chosen again when it still exists, else its documents.
  const back =
    from && profiles.data
      ? (profiles.data.find((p) => p.id === from.profile_id)?.id ?? ONE_OFF)
      : null
  const source = picked ?? back ?? search.profile ?? ''
  const profile = profiles.data?.find((p) => p.id === source)
  const loading = useSourceDocuments(from, profile, documents, setDocuments)
  const start = useMutation({
    mutationFn: async (choice?: SaveChoice): Promise<PreparationView | null> => {
      const plan = execution.data?.profile ?? 'local'
      const stored = await storeDocuments(documents)
      setDocuments(stored)
      const chosen: ProfileChoice | null = profile
        ? { kind: 'saved', id: profile.id, name: profile.name }
        : name.trim()
          ? { kind: 'new', name: name.trim() }
          : null
      const outcome = await commitProfileDocuments(client, stored, chosen, choice)
      if (outcome.kind === 'ask') return null
      return prepareDocuments(stored, { language, execution: plan, profileId: outcome.profileId })
    },
    onSuccess: (preparation) => {
      setAsking(preparation === null)
      if (!preparation) return
      // The analysis gone back from is replaced by this one.
      if (search.from) forgetCvCheckPreparation(search.from)
      rememberCvCheckPreparation(preparation.id)
      void navigate({
        to: '/cv-checks/new/$preparationId',
        params: { preparationId: preparation.id },
      })
    },
  })
  const problems = source === '' ? [] : problemsOf(documents)
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
      <UnfinishedCvChecksNotice />
      <fieldset>
        <legend className="mb-3 flex items-center gap-1 font-heading text-base font-semibold">
          {t.source} <RequiredMark />
        </legend>
        <RadioGroup
          aria-required
          value={source}
          onValueChange={(value) => {
            setPicked(value)
            // Another source starts from its own documents, not from those brought back.
            setDocuments(emptyDocuments())
            if (search.from) void navigate({ to: '/cv-checks/new', search: {}, replace: true })
          }}
          className="gap-6"
        >
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
      {source !== '' &&
        (loading.loading ? (
          <p className="flex items-center gap-2 text-muted-foreground" aria-live="polite">
            <Loader2Icon className="size-4 animate-spin" aria-hidden="true" />
            {d.loading}
          </p>
        ) : (
          <DocumentsEditor
            id="cv-check"
            documents={documents}
            language={language}
            execution={execution.data?.profile ?? 'local'}
            onChange={(update) => {
              setDocuments((current) => update(current))
            }}
          />
        ))}
      {loading.error && (
        <Alert variant="destructive">
          <AlertDescription>
            {d.loadError} {loading.error.message}
          </AlertDescription>
        </Alert>
      )}
      {source === ONE_OFF && (
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
      )}
      <div className="sticky bottom-0 z-10 -mx-6 flex flex-wrap items-center justify-between gap-3 border-t bg-background/95 px-6 py-4 backdrop-blur">
        <p className="text-sm text-muted-foreground" aria-live="polite">
          {hint}
        </p>
        <Button
          type="button"
          disabled={
            start.isPending || loading.loading || hint !== undefined || execution.data === undefined
          }
          onClick={() => {
            start.mutate(undefined)
          }}
        >
          {start.isPending ? t.analysing : t.analyse}
        </Button>
        {start.error && !asking && (
          <p role="alert" className="w-full text-sm text-destructive">
            {start.error.message}
          </p>
        )}
      </div>
      <SaveProfileDialog
        open={asking}
        profileName={profile?.name ?? ''}
        pending={start.isPending}
        error={start.error?.message}
        onConfirm={(choice) => {
          start.mutate(choice)
        }}
        onCancel={() => {
          setAsking(false)
        }}
      />
    </Page>
  )
}
