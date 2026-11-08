import * as React from 'react'
import { Dialog as DialogPrimitive } from 'radix-ui'
import { cn } from 'cn'

export const Dialog = DialogPrimitive.Root
export const DialogTitle = DialogPrimitive.Title
export const DialogDescription = DialogPrimitive.Description

export function DialogContent({ className, children, ...props }: React.ComponentProps<typeof DialogPrimitive.Content>) {
  return <DialogPrimitive.Portal><DialogPrimitive.Overlay className="fixed inset-0 z-50 bg-black/50" /><DialogPrimitive.Content className={cn('fixed top-1/2 left-1/2 z-50 max-h-[90svh] w-[calc(100%-3rem)] max-w-lg -translate-x-1/2 -translate-y-1/2 overflow-y-auto rounded-xl bg-background shadow-lg outline-none', className)} {...props}>{children}</DialogPrimitive.Content></DialogPrimitive.Portal>
}
