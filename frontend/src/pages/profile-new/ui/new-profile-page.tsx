import { useIsMutating, useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useNavigate } from '@tanstack/react-router'
import { useState } from 'react'

import { MAX_PROFILE_NAME, emptyDocuments } from '@/entities/preparation'
import type { DocumentsDraft } from '@/entities/preparation'
import { profilesQuery } from '@/entities/profile'
import {
  DocumentsEditor,
  UPLOAD_KEY,
  documentsMessages,
  problemsOf,
  profileBody,
  storeDocuments,
  useProblemText,
} from '@/features/edit-documents'
import { api } from '@/shared/api'
import { defineMessages, useMessages } from '@/shared/i18n'
import { useLanguage } from '@/shared/lib/preferences'
import { Button } from '@/shared/ui/button'
import { Card, CardContent } from '@/shared/ui/card'
import { Input } from '@/shared/ui/input'
import { Page, PageHeader } from '@/shared/ui/page-header'
import { RequiredMark } from '@/shared/ui/required-mark'

const messages = defineMessages({
  en: {
    eyebrow: 'Resource profile',
    title: 'New profile',
    description:
      'Keep a CV, a job offer and resources together, to check the CV or prepare interviews with them.',
    name: 'Profile name',
    nameMissing: 'Name the profile.',
    uploading: 'Wait for the uploads to finish.',
    save: 'Save the profile',
    saving: 'Saving…',
  },
  it: {
    eyebrow: 'Profilo delle risorse',
    title: 'Nuovo profilo',
    description:
      'Tieni insieme CV, offerta e risorse, per controllare il CV o preparare colloqui con questi documenti.',
    name: 'Nome del profilo',
    nameMissing: 'Dai un nome al profilo.',
    uploading: 'Attendi la fine dei caricamenti.',
    save: 'Salva il profilo',
    saving: 'Salvataggio…',
  },
})

/** Create a profile from its documents, without preparing an interview. */
export function NewProfilePage() {
  const t = useMessages(messages)
  const d = useMessages(documentsMessages)
  const language = useLanguage()
  const navigate = useNavigate()
  const client = useQueryClient()
  const describe = useProblemText()
  const execution = useQuery({ queryKey: ['execution-profile'], queryFn: api.executionProfile })
  const uploads = useIsMutating({ mutationKey: UPLOAD_KEY })
  const [name, setName] = useState('')
  const [documents, setDocuments] = useState<DocumentsDraft>(emptyDocuments)
  const save = useMutation({
    mutationFn: async () => api.saveProfile(profileBody(name, await storeDocuments(documents))),
    onSuccess: (profile) => {
      client.setQueryData(profilesQuery.queryKey, (old) => [profile, ...(old ?? [])])
      void navigate({
        to: '/profiles/$profileId',
        params: { profileId: profile.id },
        replace: true,
      })
    },
  })
  // A profile may hold resources only, so the CV is not required here.
  const problems = problemsOf(documents).filter((p) => p.kind !== 'cv')
  const hint =
    name.trim() === ''
      ? t.nameMissing
      : uploads > 0
        ? t.uploading
        : problems.length
          ? `${d.problems.intro} ${problems.map(describe).join('; ')}.`
          : undefined
  return (
    <Page>
      <PageHeader eyebrow={t.eyebrow} title={t.title} description={t.description} />
      <Card>
        <CardContent className="flex max-w-md flex-col gap-2">
          <label htmlFor="new-profile-name" className="flex items-center gap-1 text-sm font-medium">
            {t.name} <RequiredMark />
          </label>
          <Input
            id="new-profile-name"
            required
            maxLength={MAX_PROFILE_NAME}
            value={name}
            onChange={(event) => {
              setName(event.target.value)
            }}
          />
        </CardContent>
      </Card>
      <DocumentsEditor
        id="new-profile"
        documents={documents}
        language={language}
        execution={execution.data?.profile ?? 'local'}
        onChange={(update) => {
          setDocuments((current) => update(current))
        }}
      />
      <div className="sticky bottom-0 z-10 -mx-6 flex flex-wrap items-center justify-between gap-3 border-t bg-background/95 px-6 py-4 backdrop-blur">
        <p className="text-sm text-muted-foreground" aria-live="polite">
          {hint}
        </p>
        <Button
          type="button"
          disabled={save.isPending || hint !== undefined}
          onClick={() => {
            save.mutate()
          }}
        >
          {save.isPending ? t.saving : t.save}
        </Button>
        {save.error && (
          <p role="alert" className="w-full text-sm text-destructive">
            {save.error.message}
          </p>
        )}
      </div>
    </Page>
  )
}
