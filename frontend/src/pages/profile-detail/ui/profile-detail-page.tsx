import { useIsMutating, useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Link, useNavigate, useParams } from '@tanstack/react-router'
import { FileCheckIcon, PlayIcon } from 'lucide-react'
import { useState } from 'react'

import type { DocumentsDraft } from '@/entities/preparation'
import { profilesQuery } from '@/entities/profile'
import {
  DocumentsEditor,
  UPLOAD_KEY,
  loadProfileDocuments,
  problemsOf,
  profileBody,
  storeDocuments,
} from '@/features/edit-documents'
import { DeleteProfile, RenameProfile } from '@/features/manage-profile'
import { useStartWithProfile } from '@/features/select-profile'
import { api } from '@/shared/api'
import type { ProfileView } from '@/shared/api'
import { defineMessages, useMessages } from '@/shared/i18n'
import { shortDate } from '@/shared/lib/format'
import { useLanguage } from '@/shared/lib/preferences'
import { Button } from '@/shared/ui/button'
import { PAGE_TITLE, Page, PageHeader } from '@/shared/ui/page-header'
import { CvCheckList } from '@/widgets/cv-check-list'

const messages = defineMessages({
  en: {
    eyebrow: 'Resource profile',
    loading: 'Loading…',
    notFound: 'This profile does not exist.',
    updated: (date: string) => `Updated on ${date}`,
    use: 'New interview with this profile',
    check: 'Check the CV',
    unsaved: 'Unsaved changes',
    usesSaved: 'New interviews and CV checks use the saved version.',
    incomplete: 'Complete the highlighted documents before saving.',
    discard: 'Discard',
    save: 'Save changes',
    saving: 'Saving…',
  },
  it: {
    eyebrow: 'Profilo delle risorse',
    loading: 'Caricamento…',
    notFound: 'Questo profilo non esiste.',
    updated: (date: string) => `Aggiornato il ${date}`,
    use: 'Nuovo colloquio con questo profilo',
    check: 'Controlla il CV',
    unsaved: 'Modifiche non salvate',
    usesSaved: 'I nuovi colloqui e CV check usano la versione salvata.',
    incomplete: 'Completa i documenti evidenziati prima di salvare.',
    discard: 'Annulla modifiche',
    save: 'Salva le modifiche',
    saving: 'Salvataggio…',
  },
})

function Editor({ profile }: { profile: ProfileView }) {
  const t = useMessages(messages)
  const language = useLanguage()
  const client = useQueryClient()
  const execution = useQuery({ queryKey: ['execution-profile'], queryFn: api.executionProfile })
  const loaded = useQuery({
    queryKey: ['profile-documents', profile.id, profile.updated_at],
    queryFn: () => loadProfileDocuments(profile),
    staleTime: Infinity,
  })
  const [edited, setEdited] = useState<DocumentsDraft | null>(null)
  const uploads = useIsMutating({ mutationKey: UPLOAD_KEY })
  const documents = edited ?? loaded.data
  const save = useMutation({
    mutationFn: async (current: DocumentsDraft) => {
      const stored = await storeDocuments(current)
      return api.saveProfile(profileBody(profile.name, stored), profile.id)
    },
    onSuccess: (saved) => {
      client.setQueryData(profilesQuery.queryKey, (old) =>
        old?.map((p) => (p.id === saved.id ? saved : p)),
      )
      void client.invalidateQueries({ queryKey: ['history'] })
      setEdited(null)
    },
  })
  if (!documents)
    return (
      <p className="text-muted-foreground">{loaded.error ? loaded.error.message : t.loading}</p>
    )
  // A profile may hold resources only, so the CV is not required here.
  const problems = problemsOf(documents).filter((p) => p.kind !== 'cv')
  return (
    <>
      <DocumentsEditor
        id="profile"
        documents={documents}
        language={language}
        execution={execution.data?.profile ?? 'local'}
        onChange={(update) => {
          setEdited(update(documents))
        }}
      />
      {edited && (
        <div className="sticky bottom-0 z-10 -mx-6 flex flex-wrap items-center justify-between gap-3 border-t bg-background/95 px-6 py-4 backdrop-blur">
          <p className="text-sm">
            <span className="font-medium">{t.unsaved}</span>{' '}
            <span className="text-muted-foreground">
              {problems.length ? t.incomplete : t.usesSaved}
            </span>
          </p>
          <div className="flex gap-2">
            <Button
              type="button"
              variant="ghost"
              disabled={save.isPending}
              onClick={() => {
                setEdited(null)
              }}
            >
              {t.discard}
            </Button>
            <Button
              type="button"
              disabled={save.isPending || uploads > 0 || problems.length > 0}
              onClick={() => {
                save.mutate(edited)
              }}
            >
              {save.isPending ? t.saving : t.save}
            </Button>
          </div>
          {save.error && (
            <p role="alert" className="w-full text-sm text-destructive">
              {save.error.message}
            </p>
          )}
        </div>
      )}
    </>
  )
}

/** One saved profile: rename it, edit its documents, use it, or delete it. */
export function ProfileDetailPage() {
  const t = useMessages(messages)
  const language = useLanguage()
  const navigate = useNavigate()
  const { start, confirmation } = useStartWithProfile()
  const { profileId } = useParams({ from: '/profiles/$profileId' })
  const profiles = useQuery(profilesQuery)
  const profile = profiles.data?.find((p) => p.id === profileId)
  if (profiles.isPending) return <Page>{t.loading}</Page>
  if (!profile)
    return (
      <Page>
        <p role="alert">{t.notFound}</p>
      </Page>
    )
  return (
    <Page>
      <PageHeader
        eyebrow={t.eyebrow}
        title={<RenameProfile profile={profile} nameAs="h1" className={`${PAGE_TITLE} truncate`} />}
        description={t.updated(shortDate(profile.updated_at, language))}
        actions={
          <>
            <Button
              type="button"
              className="bg-brand text-brand-foreground hover:bg-brand/90"
              onClick={() => {
                start(profile)
              }}
            >
              <PlayIcon data-icon="inline-start" />
              {t.use}
            </Button>
            {profile.cv && (
              <Button asChild variant="outline">
                <Link to="/cv-checks/new" search={{ profile: profile.id }}>
                  <FileCheckIcon data-icon="inline-start" />
                  {t.check}
                </Link>
              </Button>
            )}
            <DeleteProfile
              profile={profile}
              onDeleted={() => void navigate({ to: '/profiles', replace: true })}
            />
          </>
        }
      />
      <CvCheckList pageSize={3} profileId={profile.id} />
      <Editor key={`${profile.id}-${String(profile.updated_at)}`} profile={profile} />
      {confirmation}
    </Page>
  )
}
