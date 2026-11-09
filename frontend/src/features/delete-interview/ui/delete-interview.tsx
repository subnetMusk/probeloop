import { useMutation, useQueryClient } from '@tanstack/react-query'
import { Trash2Icon } from 'lucide-react'
import { useState } from 'react'

import { api } from '@/shared/api'
import { defineMessages, useMessages } from '@/shared/i18n'
import { Button } from '@/shared/ui/button'
import { ConfirmDialog } from '@/shared/ui/confirm-dialog'

const messages = defineMessages({
  en: {
    delete: (name: string) => `Delete the interview: ${name}`,
    title: 'Delete this interview?',
    text: 'Its transcript, recordings and reports are deleted from this computer. This cannot be undone.',
    confirm: 'Delete interview',
    cancel: 'Cancel',
  },
  it: {
    delete: (name: string) => `Elimina il colloquio: ${name}`,
    title: 'Eliminare questo colloquio?',
    text: 'Trascritto, registrazioni e report vengono eliminati da questo computer. L’operazione non si può annullare.',
    confirm: 'Elimina colloquio',
    cancel: 'Annulla',
  },
})

/** Delete an interview with its recordings and reports, after a confirmation. */
export function DeleteInterview({ sessionId, name }: { sessionId: string; name: string }) {
  const t = useMessages(messages)
  const client = useQueryClient()
  const [open, setOpen] = useState(false)
  const remove = useMutation({
    mutationFn: () => api.deleteSession(sessionId),
    onSuccess: () => {
      setOpen(false)
      void client.invalidateQueries({ queryKey: ['history'] })
      void client.invalidateQueries({ queryKey: ['progress'] })
    },
  })
  return (
    <>
      <Button
        type="button"
        variant="ghost"
        size="icon-sm"
        aria-label={t.delete(name)}
        onClick={() => {
          setOpen(true)
        }}
      >
        <Trash2Icon />
      </Button>
      <ConfirmDialog
        open={open}
        title={t.title}
        description={t.text}
        confirm={t.confirm}
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
