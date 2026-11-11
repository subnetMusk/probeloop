import { LoaderCircleIcon, UploadIcon } from 'lucide-react'
import { useState } from 'react'
import type { DragEvent } from 'react'

import { defineMessages, useMessages } from '@/shared/i18n'
import { cn } from '@/shared/lib/utils'

const messages = defineMessages({
  en: {
    drop: 'Drag a file here',
    or: 'or',
    browse: 'browse your computer',
    release: 'Drop to upload',
    replace: 'Drag another file here to replace it, or browse',
    uploading: 'Uploading…',
    tooLarge: (mb: number) => `The file is larger than ${String(mb)} MB.`,
    unsupported: 'This file type is not supported.',
  },
  it: {
    drop: 'Trascina qui un file',
    or: 'oppure',
    browse: 'sfoglia il computer',
    release: 'Rilascia per caricare',
    replace: 'Trascina qui un altro file per sostituirlo, oppure sfoglia',
    uploading: 'Caricamento…',
    tooLarge: (mb: number) => `Il file supera i ${String(mb)} MB.`,
    unsupported: 'Questo tipo di file non è supportato.',
  },
})

function accepted(file: File, accept: string): boolean {
  const name = file.name.toLowerCase()
  return accept
    .split(',')
    .map((item) => item.trim().toLowerCase())
    .some((item) => item.startsWith('.') && name.endsWith(item))
}

/**
 * A file upload area: a dashed box with the upload icon. Dropping a file on it, or clicking it
 * (which opens the file chooser, like "Browse"), hands the file to `onFile`. The real file input
 * stays in the page, visually hidden, so keyboards and assistive technology use it as usual.
 */
export function FileDrop({
  id,
  accept,
  maxBytes,
  busy = false,
  replacing = false,
  describedBy,
  onFile,
}: {
  id: string
  accept: string
  maxBytes: number
  busy?: boolean
  replacing?: boolean // a file was already loaded: the area offers to replace it
  describedBy?: string
  onFile: (file: File) => void
}) {
  const t = useMessages(messages)
  const [dragging, setDragging] = useState(false)
  const [problem, setProblem] = useState<string | null>(null)
  const take = (file: File | undefined) => {
    if (!file) return
    if (!accepted(file, accept)) {
      setProblem(t.unsupported)
      return
    }
    if (file.size > maxBytes) {
      setProblem(t.tooLarge(Math.round(maxBytes / 1_000_000)))
      return
    }
    setProblem(null)
    onFile(file)
  }
  const over = (event: DragEvent<HTMLLabelElement>) => {
    event.preventDefault()
    if (!busy) setDragging(true)
  }
  return (
    <div className="flex flex-col gap-1.5">
      <input
        id={id}
        type="file"
        accept={accept}
        disabled={busy}
        aria-describedby={describedBy}
        className="peer sr-only"
        onChange={(event) => {
          take(event.target.files?.[0])
          event.currentTarget.value = ''
        }}
      />
      <label
        htmlFor={id}
        data-testid={`${id}-drop`}
        data-dragging={dragging || undefined}
        onDragEnter={over}
        onDragOver={over}
        onDragLeave={() => {
          setDragging(false)
        }}
        onDrop={(event) => {
          event.preventDefault()
          setDragging(false)
          if (!busy) take(event.dataTransfer.files[0])
        }}
        className={cn(
          'flex cursor-pointer flex-col items-center justify-center gap-2 rounded-xl border-2 border-dashed border-input/70 bg-card px-4 text-center transition-colors hover:border-brand/60 hover:bg-brand/5 peer-focus-visible:border-brand peer-focus-visible:ring-3 peer-focus-visible:ring-ring/50 peer-disabled:cursor-progress',
          replacing ? 'py-4' : 'py-7',
          dragging && 'border-brand bg-brand/10',
        )}
      >
        {busy ? (
          <LoaderCircleIcon className="size-7 animate-spin text-brand-text" aria-hidden />
        ) : (
          <span
            aria-hidden
            className={cn(
              'flex items-center justify-center rounded-full bg-brand/10 text-brand-text transition-transform',
              replacing ? 'size-9' : 'size-11',
              dragging && 'scale-110',
            )}
          >
            <UploadIcon className={replacing ? 'size-4' : 'size-5'} />
          </span>
        )}
        <span className="text-sm">
          {busy ? (
            t.uploading
          ) : dragging ? (
            <strong className="font-medium">{t.release}</strong>
          ) : replacing ? (
            <span className="text-muted-foreground">{t.replace}</span>
          ) : (
            <>
              <strong className="font-medium">{t.drop}</strong>{' '}
              <span className="text-muted-foreground">{t.or}</span>{' '}
              <span className="font-medium text-brand-text underline underline-offset-4">
                {t.browse}
              </span>
            </>
          )}
        </span>
      </label>
      {problem && (
        <p role="alert" className="text-sm text-destructive">
          {problem}
        </p>
      )}
    </div>
  )
}
