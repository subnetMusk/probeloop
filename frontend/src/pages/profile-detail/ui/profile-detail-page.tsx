import { useIsMutating, useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useNavigate, useParams } from '@tanstack/react-router'
import { PlayIcon } from 'lucide-react'
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

const messages = defineMessages({
  en: {
    eyebrow: 'Resource profile',
    loading: 'Loading…',
    notFound: 'This profile does not exist.',
    updated: (date: string) => `Updated on ${date}`,
    use: 'New interview with this profile',
    unsaved: 'Unsaved changes',
    usesSaved: 'A new interview uses the saved version.',
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
    unsaved: 'Modifiche non salvate',
    usesSaved: 'Un nuovo colloquio usa la versione salvata.',
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
  const start = useStartWithProfile()
  const { profileId } = useParams({ from: '/profiles/$profileId' })
  const profiles = useQuery(profilesQuery)
  const profile = profiles.data?.find((p) => p.id === profileId)
  if (profiles.isPending) return <main className="mx-auto max-w-5xl px-6 py-8">{t.loading}</main>
  if (!profile)
    return (
      <main className="mx-auto max-w-5xl px-6 py-8">
        <p role="alert">{t.notFound}</p>
      </main>
    )
  return (
    <main className="mx-auto flex w-full max-w-5xl flex-col gap-6 px-6 py-8">
      <header className="flex flex-wrap items-end justify-between gap-4">
        <div className="flex min-w-0 flex-col gap-1">
          <p className="text-sm font-medium text-brand-text">{t.eyebrow}</p>
          <RenameProfile
            profile={profile}
            nameAs="h1"
            className="truncate text-3xl font-semibold tracking-tight"
          />
          <p className="text-muted-foreground">
            {t.updated(shortDate(profile.updated_at, language))}
          </p>
        </div>
        <div className="flex items-center gap-2">
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
          <DeleteProfile
            profile={profile}
            onDeleted={() => void navigate({ to: '/profiles', replace: true })}
          />
        </div>
      </header>
      <Editor key={`${profile.id}-${String(profile.updated_at)}`} profile={profile} />
    </main>
  )
}
