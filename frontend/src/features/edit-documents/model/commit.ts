import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import type { QueryClient } from '@tanstack/react-query'
import { useEffect, useState } from 'react'

import { getDraft, preparationKeyOf, useDraft } from '@/entities/preparation'
import type { DocumentsDraft, ProfileChoice } from '@/entities/preparation'
import { profilesQuery } from '@/entities/profile'
import { api } from '@/shared/api'
import type { ProfileView } from '@/shared/api'
import {
  differsFrom,
  loadProfileDocuments,
  prepareDocuments,
  profileBody,
  storeDocuments,
} from './documents'

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
  const preparation = await prepareDocuments(documents, {
    language: settings.language,
    execution: settings.execution,
    profileId,
  })
  useDraft.getState().startPreparation(preparation.id, key)
}

/** What saving edited documents gave: a question for the user first, or the profile to use. */
export type ProfileOutcome =
  { kind: 'ask' } | { kind: 'done'; profileId: string | null; created: ProfileView | null }

/**
 * Save stored documents as the profile choice says: a new profile is created; a saved profile
 * whose documents changed needs the user's `choice` first (overwrite it, save a new profile, or
 * use the changes once). The wizard and the CV check both use it.
 */
export async function commitProfileDocuments(
  client: QueryClient,
  stored: DocumentsDraft,
  chosen: ProfileChoice | null,
  choice?: SaveChoice,
): Promise<ProfileOutcome> {
  let profileId: string | null = null
  let created: ProfileView | null = null
  if (chosen?.kind === 'new') {
    created = await api.saveProfile(profileBody(chosen.name, stored))
    profileId = created.id
  } else if (chosen?.kind === 'saved') {
    const current = (await client.query(profilesQuery)).find((p) => p.id === chosen.id)
    profileId = current?.id ?? null
    if (current && differsFrom(stored, current)) {
      if (!choice) return { kind: 'ask' }
      if (choice.kind === 'overwrite')
        await api.saveProfile(profileBody(current.name, stored), current.id)
      else if (choice.kind === 'new') {
        created = await api.saveProfile(profileBody(choice.name, stored))
        profileId = created.id
      }
    }
  }
  void client.invalidateQueries({ queryKey: profilesQuery.queryKey })
  return { kind: 'done', profileId, created }
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
      const outcome = await commitProfileDocuments(client, stored, getDraft().profile, choice)
      if (outcome.kind === 'ask') return 'ask'
      if (outcome.created) {
        const profile = outcome.created
        actions.chooseProfile({ kind: 'saved', id: profile.id, name: profile.name })
        actions.updateDocuments((d) => ({ ...d, loadedFrom: profile.id }))
      }
      const draft = getDraft()
      if (draft.preparationId === null || draft.preparationKey !== preparationKeyOf(draft))
        await startAnalysis(outcome.profileId)
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
