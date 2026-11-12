import { useNavigate } from '@tanstack/react-router'
import { useState } from 'react'
import type { ReactNode } from 'react'

import { getDraft, useDraft } from '@/entities/preparation'
import type { ProfileView } from '@/shared/api'
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

/**
 * Start a new preparation from a saved profile: its documents load in the documents step. A
 * preparation in progress is replaced only after a confirmation, rendered by `confirmation`.
 */
export function useStartWithProfile(): {
  start: (profile: ProfileView) => void
  confirmation: ReactNode
} {
  const t = useMessages(messages)
  const navigate = useNavigate()
  const [asking, setAsking] = useState<ProfileView | null>(null)
  const go = (profile: ProfileView) => {
    const draft = useDraft.getState()
    draft.reset()
    draft.chooseProfile({ kind: 'saved', id: profile.id, name: profile.name })
    setAsking(null)
    void navigate({ to: '/new-interview' })
  }
  const draft = getDraft()
  const inProgress = draft.settingsDone || draft.profile !== null
  return {
    start: (profile) => {
      if (inProgress) setAsking(profile)
      else go(profile)
    },
    confirmation: (
      <ConfirmDialog
        open={asking !== null}
        title={t.title}
        description={t.text(asking?.name ?? '')}
        confirm={t.confirm}
        cancel={t.cancel}
        pending={false}
        tone="default"
        onConfirm={() => {
          if (asking) go(asking)
        }}
        onCancel={() => {
          setAsking(null)
        }}
      />
    ),
  }
}
