import { useNavigate } from '@tanstack/react-router'
import { useState } from 'react'
import type { ReactNode } from 'react'

import { getDraft, useDraft } from '@/entities/preparation'
import type { ProfileView, RoleProfileData } from '@/shared/api'
import { defineMessages, useMessages } from '@/shared/i18n'
import { ConfirmDialog } from '@/shared/ui/confirm-dialog'

const messages = defineMessages({
  en: {
    title: 'Replace the interview you are preparing?',
    text: (name: string) =>
      `A new interview with “${name}” starts over: the settings and documents of the preparation in progress are discarded.`,
    confirm: 'Start over',
    cancel: 'Keep preparing',
  },
  it: {
    title: 'Sostituire il colloquio che stai preparando?',
    text: (name: string) =>
      `Un nuovo colloquio con «${name}» riparte da capo: impostazioni e documenti della preparazione in corso vengono scartati.`,
    confirm: 'Ricomincia',
    cancel: 'Continua a preparare',
  },
})

/** The context a CV check approved, to practise an interview on it. */
export interface ApprovedContext {
  snapshotId: string
  /** How the check is named to the user, such as the CV's file name. */
  name: string
  profileId: string | null
  role: RoleProfileData | null
}

/**
 * Start a new preparation filled by `fill`. A preparation in progress is replaced only after a
 * confirmation, rendered by `confirmation`.
 */
function useReplacePreparation<T>(
  fill: (value: T) => void,
  nameOf: (value: T) => string,
): { start: (value: T) => void; confirmation: ReactNode } {
  const t = useMessages(messages)
  const navigate = useNavigate()
  const [asking, setAsking] = useState<{ value: T } | null>(null)
  const go = (value: T) => {
    useDraft.getState().reset()
    fill(value)
    setAsking(null)
    void navigate({ to: '/new-interview' })
  }
  const draft = getDraft()
  const inProgress = draft.settingsDone || draft.profile !== null
  return {
    start: (value) => {
      if (inProgress) setAsking({ value })
      else go(value)
    },
    confirmation: (
      <ConfirmDialog
        open={asking !== null}
        title={t.title}
        description={t.text(asking ? nameOf(asking.value) : '')}
        confirm={t.confirm}
        cancel={t.cancel}
        pending={false}
        tone="default"
        onConfirm={() => {
          if (asking) go(asking.value)
        }}
        onCancel={() => {
          setAsking(null)
        }}
      />
    ),
  }
}

/** Start a new preparation from a saved profile: its documents load in the documents step. */
export function useStartWithProfile() {
  return useReplacePreparation(
    (profile: ProfileView) => {
      useDraft.getState().chooseProfile({ kind: 'saved', id: profile.id, name: profile.name })
    },
    (profile) => profile.name,
  )
}

/**
 * Start a new preparation on the context a CV check approved: after the settings it goes
 * straight to the final check, and the interview uses the check's practice questions.
 */
export function useStartWithContext() {
  return useReplacePreparation(
    (context: ApprovedContext) => {
      const draft = useDraft.getState()
      draft.chooseProfile({
        kind: 'approved',
        snapshotId: context.snapshotId,
        name: context.name,
        profileId: context.profileId,
      })
      draft.setRoleProfile(context.role)
      draft.setSnapshot(context.snapshotId)
    },
    (context) => context.name,
  )
}
