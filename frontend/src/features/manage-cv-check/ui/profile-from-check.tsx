import { useMutation, useQueryClient } from '@tanstack/react-query'
import { BookmarkPlusIcon } from 'lucide-react'
import { useState } from 'react'

import { MAX_PROFILE_NAME } from '@/entities/preparation'
import { profilesQuery } from '@/entities/profile'
import { api } from '@/shared/api'
import type { ProfileView } from '@/shared/api'
import { useMessages } from '@/shared/i18n'
import { Button } from '@/shared/ui/button'
import { Dialog, DialogContent, DialogDescription, DialogTitle } from '@/shared/ui/dialog'
import { Input } from '@/shared/ui/input'
import { RequiredMark } from '@/shared/ui/required-mark'
import { cvCheckMessages } from './messages'

/** Save the documents of a CV check as a new profile, which then owns the check. */
export function ProfileFromCheck({
  snapshotId,
  onCreated,
}: {
  snapshotId: string
  onCreated?: (profile: ProfileView) => void
}) {
  const t = useMessages(cvCheckMessages)
  const client = useQueryClient()
  const [open, setOpen] = useState(false)
  const [name, setName] = useState('')
  const save = useMutation({
    mutationFn: () => api.profileFromCheck(snapshotId, name.trim()),
    onSuccess: (profile) => {
      client.setQueryData(profilesQuery.queryKey, (old) => [profile, ...(old ?? [])])
      void client.invalidateQueries({ queryKey: ['cv-reviews', snapshotId] })
      void client.invalidateQueries({ queryKey: ['history'] })
      void client.invalidateQueries({ queryKey: ['progress'] })
      setOpen(false)
      onCreated?.(profile)
    },
  })
  const close = () => {
    if (!save.isPending) setOpen(false)
  }
  return (
    <>
      <Button
        type="button"
        variant="outline"
        onClick={() => {
          setOpen(true)
        }}
      >
        <BookmarkPlusIcon data-icon="inline-start" />
        {t.save}
      </Button>
      <Dialog
        open={open}
        onOpenChange={(next) => {
          if (!next) close()
        }}
      >
        <DialogContent className="flex flex-col gap-4 p-6">
          <div className="flex flex-col gap-1">
            <DialogTitle className="font-heading text-lg font-semibold">{t.saveTitle}</DialogTitle>
            <DialogDescription className="text-sm text-muted-foreground">
              {t.saveText}
            </DialogDescription>
          </div>
          <form
            noValidate
            className="flex flex-col gap-4"
            onSubmit={(event) => {
              event.preventDefault()
              if (name.trim()) save.mutate()
            }}
          >
            <div className="flex flex-col gap-2">
              <label
                htmlFor="profile-from-check-name"
                className="flex items-center gap-1 text-sm font-medium"
              >
                {t.name} <RequiredMark />
              </label>
              <Input
                id="profile-from-check-name"
                required
                maxLength={MAX_PROFILE_NAME}
                disabled={save.isPending}
                value={name}
                onChange={(event) => {
                  setName(event.target.value)
                }}
              />
            </div>
            {save.error && (
              <p role="alert" className="text-sm text-destructive">
                {save.error.message}
              </p>
            )}
            <div className="flex justify-end gap-2">
              <Button type="button" variant="ghost" disabled={save.isPending} onClick={close}>
                {t.cancel}
              </Button>
              <Button type="submit" disabled={save.isPending || name.trim() === ''}>
                {t.confirmSave}
              </Button>
            </div>
          </form>
        </DialogContent>
      </Dialog>
    </>
  )
}
