import { useMutation, useQueryClient } from '@tanstack/react-query'
import { Trash2Icon } from 'lucide-react'
import { useState } from 'react'

import { api } from '@/shared/api'
import { useMessages } from '@/shared/i18n'
import { Button } from '@/shared/ui/button'
import { ConfirmDialog } from '@/shared/ui/confirm-dialog'
import { cvCheckMessages } from './messages'

/**
 * Delete every version of a CV check after a confirmation. The server keeps the documents that a
 * saved profile or an interview still uses.
 */
export function DeleteCvCheck({
  snapshotId,
  onDeleted,
}: {
  snapshotId: string
  onDeleted?: () => void
}) {
  const t = useMessages(cvCheckMessages)
  const client = useQueryClient()
  const [open, setOpen] = useState(false)
  const remove = useMutation({
    mutationFn: () => api.deleteCvCheck(snapshotId),
    onSuccess: () => {
      for (const key of ['cv-reviews', 'cv-jobs', 'snapshot'])
        client.removeQueries({ queryKey: [key, snapshotId] })
      void client.invalidateQueries({ queryKey: ['history'] })
      void client.invalidateQueries({ queryKey: ['progress'] })
      setOpen(false)
      onDeleted?.()
    },
  })
  return (
    <>
      <Button
        type="button"
        variant="outline"
        onClick={() => {
          setOpen(true)
        }}
      >
        <Trash2Icon data-icon="inline-start" />
        {t.delete}
      </Button>
      <ConfirmDialog
        open={open}
        title={t.deleteTitle}
        description={t.deleteText}
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
