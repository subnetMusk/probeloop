import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useEffect, useState } from 'react'

import { getDraft, jobModeOf, preparationKeyOf, useDraft } from '@/entities/preparation'
import type { ProfileChoice } from '@/entities/preparation'
import { profilesQuery } from '@/entities/profile'
import { api } from '@/shared/api'
import type { ProfileView } from '@/shared/api'
import { differsFrom, loadProfileDocuments, profileBody, storeDocuments } from './documents'

/** What to do with a saved profile whose documents were changed for this interview. */
export type SaveChoice = { kind: 'overwrite' } | { kind: 'new'; name: string } | { kind: 'once' }

/**
 * Fill the editor with the documents of the chosen saved profile, once per choice: coming back
 * to the step keeps the user's edits.
 */
export function useProfileDocuments(choice: ProfileChoice | null) {
  const loadedFrom = useDraft((draft) => draft.documents.loadedFrom)
  const updateDocuments = useDraft((draft) => draft.updateDocuments)
  const profiles = useQuery(profilesQuery)
  const wanted = choice?.kind === 'saved' && loadedFrom !== choice.id ? choice.id : null
  const profile = profiles.data?.find((p) => p.id === wanted)
  const load = useQuery({
    queryKey: ['profile-documents', profile?.id, profile?.updated_at],
    queryFn: () => loadProfileDocuments(profile as ProfileView),
    enabled: profile !== undefined,
    staleTime: Infinity,
  })
  useEffect(() => {
    if (load.data && load.data.loadedFrom === wanted) updateDocuments(() => load.data)
  }, [load.data, wanted, updateDocuments])
  return {
    loading: wanted !== null && (profiles.isPending || load.isPending),
    error: profiles.error ?? load.error,
  }
}

/** Analyse the stored documents of the draft in a new preparation. */
export async function startAnalysis(profileId: string | null): Promise<void> {
  const draft = getDraft()
  const key = preparationKeyOf(draft)
  const { settings, documents } = draft
  if (key === null || settings.execution === null) throw new Error('documents not stored')
  const offer = documents.offerSource === 'none' ? null : documents.offer
  const preparation = await api.prepare({
    language: settings.language,
    job_mode: jobModeOf(documents),
    cv_id: documents.cv.documentId,
    job_offer_id: offer?.documentId ?? null,
    resources: documents.resources.map((r) => ({
      title: r.title.trim(),
      document_id: r.documentId ?? '',
    })),
    profile_id: profileId,
    execution_profile: settings.execution,
  })
  useDraft.getState().startPreparation(preparation.id, key)
}

/**
 * Continue from the documents step: store the edited documents, save the profile as chosen, and
 * start a new analysis unless the documents and settings are those of the current preparation.
 * A saved profile whose documents changed needs the user's choice first (`asking`).
 */
export function useCommitDocuments(onDone: () => void) {
  const client = useQueryClient()
  const [asking, setAsking] = useState(false)
  const commit = useMutation({
    mutationFn: async (choice?: SaveChoice): Promise<'ask' | 'done'> => {
      const actions = useDraft.getState()
      const stored = await storeDocuments(getDraft().documents)
      actions.updateDocuments(() => stored)
      const chosen = getDraft().profile
      const keep = (profile: ProfileView) => {
        actions.chooseProfile({ kind: 'saved', id: profile.id, name: profile.name })
        actions.updateDocuments((d) => ({ ...d, loadedFrom: profile.id }))
        return profile.id
      }
      let profileId: string | null = null
      if (chosen?.kind === 'new') {
        profileId = keep(await api.saveProfile(profileBody(chosen.name, stored)))
      } else if (chosen?.kind === 'saved') {
        const current = (await client.query(profilesQuery)).find((p) => p.id === chosen.id)
        profileId = current?.id ?? null
        if (current && differsFrom(stored, current)) {
          if (!choice) return 'ask'
          if (choice.kind === 'overwrite')
            await api.saveProfile(profileBody(current.name, stored), current.id)
          else if (choice.kind === 'new')
            profileId = keep(await api.saveProfile(profileBody(choice.name, stored)))
        }
      }
      void client.invalidateQueries({ queryKey: profilesQuery.queryKey })

      const draft = getDraft()
      if (draft.preparationId === null || draft.preparationKey !== preparationKeyOf(draft))
        await startAnalysis(profileId)
      return 'done'
    },
    onSuccess: (result) => {
      setAsking(result === 'ask')
      if (result === 'done') onDone()
    },
  })
  return {
    commit,
    asking,
    cancel: () => {
      setAsking(false)
    },
  }
}
