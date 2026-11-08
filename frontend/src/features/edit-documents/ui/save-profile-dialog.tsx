import { useState } from 'react'

import { MAX_PROFILE_NAME } from '@/entities/preparation'
import { defineMessages, useMessages } from '@/shared/i18n'
import { Button } from '@/shared/ui/button'
import { ChoiceCard } from '@/shared/ui/choice-card'
import { Dialog, DialogContent, DialogDescription, DialogTitle } from '@/shared/ui/dialog'
import { Input } from '@/shared/ui/input'
import { RadioGroup } from '@/shared/ui/radio-group'
import { RequiredMark } from '@/shared/ui/required-mark'
import type { SaveChoice } from '../model/commit'

const messages = defineMessages({
  en: {
    title: 'Keep these changes in the profile?',
    description: (name: string) => `You changed the documents loaded from “${name}”.`,
    overwrite: (name: string) => `Overwrite “${name}”`,
    overwriteHint: 'The next interviews with this profile use the new documents.',
    saveNew: 'Save as a new profile',
    saveNewHint: (name: string) => `“${name}” stays as it is.`,
    once: 'Use them for this interview only',
    onceHint: 'The profile stays as it is.',
    name: 'Name of the new profile',
    confirm: 'Continue',
    cancel: 'Cancel',
  },
  it: {
    title: 'Salvare queste modifiche nel profilo?',
    description: (name: string) => `Hai modificato i documenti caricati da «${name}».`,
    overwrite: (name: string) => `Sovrascrivi «${name}»`,
    overwriteHint: 'I prossimi colloqui con questo profilo useranno i nuovi documenti.',
    saveNew: 'Salva come nuovo profilo',
    saveNewHint: (name: string) => `«${name}» resta com’è.`,
    once: 'Usale solo per questo colloquio',
    onceHint: 'Il profilo resta com’è.',
    name: 'Nome del nuovo profilo',
    confirm: 'Continua',
    cancel: 'Annulla',
  },
})

/** Asks what to do with a saved profile whose documents were changed. */
export function SaveProfileDialog({
  open,
  profileName,
  pending,
  error,
  onConfirm,
  onCancel,
}: {
  open: boolean
  profileName: string
  pending: boolean
  error: string | undefined
  onConfirm: (choice: SaveChoice) => void
  onCancel: () => void
}) {
  const t = useMessages(messages)
  const [kind, setKind] = useState<SaveChoice['kind']>('overwrite')
  const [name, setName] = useState('')
  const valid = kind !== 'new' || name.trim() !== ''
  return (
    <Dialog
      open={open}
      onOpenChange={(next) => {
        if (!next && !pending) onCancel()
      }}
    >
      <DialogContent className="flex flex-col gap-4 p-6">
        <div className="flex flex-col gap-1">
          <DialogTitle className="font-heading text-lg font-semibold">{t.title}</DialogTitle>
          <DialogDescription className="text-sm text-muted-foreground">
            {t.description(profileName)}
          </DialogDescription>
        </div>
        <form
          noValidate
          className="flex flex-col gap-4"
          onSubmit={(event) => {
            event.preventDefault()
            if (!valid) return
            onConfirm(kind === 'new' ? { kind, name: name.trim() } : { kind })
          }}
        >
          <fieldset disabled={pending} className="flex flex-col gap-3">
            <RadioGroup
              aria-label={t.title}
              value={kind}
              onValueChange={(value) => {
                if (value === 'overwrite' || value === 'new' || value === 'once') setKind(value)
              }}
            >
              <ChoiceCard
                id="save-profile-overwrite"
                value="overwrite"
                title={t.overwrite(profileName)}
                description={t.overwriteHint}
              />
              <ChoiceCard
                id="save-profile-new"
                value="new"
                title={t.saveNew}
                description={t.saveNewHint(profileName)}
              />
              <ChoiceCard
                id="save-profile-once"
                value="once"
                title={t.once}
                description={t.onceHint}
              />
            </RadioGroup>
            {kind === 'new' && (
              <div className="flex flex-col gap-2">
                <label
                  htmlFor="save-profile-name"
                  className="flex items-center gap-1 text-sm font-medium"
                >
                  {t.name} <RequiredMark />
                </label>
                <Input
                  id="save-profile-name"
                  required
                  maxLength={MAX_PROFILE_NAME}
                  value={name}
                  onChange={(event) => {
                    setName(event.target.value)
                  }}
                />
              </div>
            )}
          </fieldset>
          {error && (
            <p role="alert" className="text-sm text-destructive">
              {error}
            </p>
          )}
          <div className="flex justify-end gap-2">
            <Button type="button" variant="ghost" disabled={pending} onClick={onCancel}>
              {t.cancel}
            </Button>
            <Button type="submit" disabled={!valid || pending}>
              {t.confirm}
            </Button>
          </div>
        </form>
      </DialogContent>
    </Dialog>
  )
}
