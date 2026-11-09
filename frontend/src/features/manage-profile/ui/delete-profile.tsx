import { useMutation, useQueryClient } from '@tanstack/react-query'
import { Trash2Icon } from 'lucide-react'
import { useState } from 'react'

import { profilesQuery } from '@/entities/profile'
import { api } from '@/shared/api'
import type { ProfileView } from '@/shared/api'
import { useMessages } from '@/shared/i18n'
import { Button } from '@/shared/ui/button'
import { ConfirmDialog } from '@/shared/ui/confirm-dialog'
import { manageMessages } from './messages'

/** Delete a profile after a confirmation. Its documents stay with earlier preparations. */
export function DeleteProfile({
  profile,
  onDeleted,
}: {
  profile: ProfileView
  onDeleted?: () => void
}) {
  const t = useMessages(manageMessages)
  const client = useQueryClient()
  const [open, setOpen] = useState(false)
  const remove = useMutation({
    mutationFn: () => api.deleteProfile(profile.id),
    onSuccess: () => {
      client.setQueryData(profilesQuery.queryKey, (old) => old?.filter((p) => p.id !== profile.id))
      void client.invalidateQueries({ queryKey: ['history'] })
      setOpen(false)
      onDeleted?.()
    },
  })
  return (
    <>
      <Button
        type="button"
        variant="ghost"
        size="icon-sm"
        aria-label={t.delete(profile.name)}
        onClick={() => {
          setOpen(true)
        }}
      >
        <Trash2Icon />
      </Button>
      <ConfirmDialog
        open={open}
        title={t.deleteTitle}
        description={t.deleteText(profile.name)}
        confirm={t.confirmDelete}
        cancel={t.cancel}
        pending={remove.isPending}
        error={remove.error?.message}
        onConfirm={() => {
          remove.mutate()
        }}
        onCancel={() => {
          setOpen(false)
        }}
      />
    </>
  )
}
