import type { ReactNode } from 'react'

import { Button } from './button'
import { Dialog, DialogContent, DialogDescription, DialogTitle } from './dialog'

/** Ask before an action that cannot be undone. */
export function ConfirmDialog({
  open,
  title,
  description,
  confirm,
  cancel,
  pending,
  error,
  onConfirm,
  onCancel,
}: {
  open: boolean
  title: string
  description: ReactNode
  confirm: string
  cancel: string
  pending: boolean
  error?: string
  onConfirm: () => void
  onCancel: () => void
}) {
  return (
    <Dialog
      open={open}
      onOpenChange={(next) => {
        if (!next && !pending) onCancel()
      }}
    >
      <DialogContent className="flex flex-col gap-4 p-6">
        <DialogTitle className="font-heading text-lg font-semibold">{title}</DialogTitle>
        <DialogDescription className="text-sm text-muted-foreground">{description}</DialogDescription>
        {error && (
          <p role="alert" className="text-sm text-destructive">
            {error}
          </p>
        )}
        <div className="flex justify-end gap-2">
          <Button type="button" variant="ghost" disabled={pending} onClick={onCancel}>
            {cancel}
          </Button>
          <Button type="button" variant="destructive" disabled={pending} onClick={onConfirm}>
            {confirm}
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  )
}
