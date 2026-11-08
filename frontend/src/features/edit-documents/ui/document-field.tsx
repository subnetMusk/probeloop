import { useMutation } from '@tanstack/react-query'
import { FileTextIcon, TriangleAlertIcon } from 'lucide-react'

import { emptySlot, isSaved } from '@/entities/preparation'
import type { DocumentSlot } from '@/entities/preparation'
import { api } from '@/shared/api'
import { useMessages } from '@/shared/i18n'
import { Button } from '@/shared/ui/button'
import { Input } from '@/shared/ui/input'
import { RequiredMark } from '@/shared/ui/required-mark'
import { Textarea } from '@/shared/ui/textarea'
import { ACCEPTED_FILES, MAX_TEXT, MAX_TITLE, UPLOAD_KEY, slotOf } from '../model/documents'
import { documentsMessages } from './messages'

const fileTitle = (name: string) => name.replace(/\.[^.]+$/, '').slice(0, MAX_TITLE) || name

/**
 * One document: its text, editable, and a file upload. A file is stored as soon as it is chosen
 * and its extracted text fills the editor; edits to it become a revision when the step continues.
 */
export function DocumentField({
  id,
  kind,
  label,
  required = false,
  upload: canUpload = true,
  slot,
  onChange,
}: {
  id: string
  kind: 'cv' | 'job_offer' | 'resource'
  label: string
  required?: boolean
  /** False for text that must stay typed, such as a drafted job offer. */
  upload?: boolean
  slot: DocumentSlot
  onChange: (slot: DocumentSlot) => void
}) {
  const t = useMessages(documentsMessages)
  const upload = useMutation({
    mutationKey: UPLOAD_KEY,
    mutationFn: async (file: File) => {
      const title = slot.title.trim() || fileTitle(file.name)
      const view = await api.uploadDocument(kind, title, file)
      const { text } = await api.documentText(view.id)
      return slotOf(view, text)
    },
    onSuccess: onChange,
  })
  const edited = slot.documentId !== null && slot.hasOriginal && !isSaved(slot)
  const hint = `${id}-hint`
  return (
    <div className="flex flex-col gap-2">
      <label htmlFor={`${id}-text`} className="flex items-center gap-1 text-sm font-medium">
        {label} {required && <RequiredMark />}
      </label>
      {slot.filename && (
        <p className="flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
          <FileTextIcon className="size-3.5" aria-hidden="true" />
          <span>{t.field.fromFile(slot.filename)}</span>
          {slot.hasOriginal && slot.documentId && (
            <a
              href={`/api/documents/${encodeURIComponent(slot.documentId)}/original`}
              target="_blank"
              rel="noreferrer"
              className="text-brand-text underline"
            >
              {t.field.original}
            </a>
          )}
        </p>
      )}
      <Textarea
        id={`${id}-text`}
        className="min-h-40"
        required={required}
        maxLength={MAX_TEXT}
        value={slot.text}
        disabled={upload.isPending}
        onChange={(event) => {
          onChange({ ...slot, text: event.target.value })
        }}
      />
      {edited && <p className="text-xs text-muted-foreground">{t.field.edited}</p>}
      {slot.warnings.length > 0 && (
        <div role="note" className="flex gap-2 rounded-lg border border-warning/60 p-3 text-sm">
          <TriangleAlertIcon className="mt-0.5 size-4 text-warning" aria-hidden="true" />
          <div>
            <p className="font-medium">{t.field.warning}</p>
            {slot.warnings.map((warning) => (
              <p key={warning}>{warning}</p>
            ))}
          </div>
        </div>
      )}
      <div className="flex flex-wrap items-end gap-3">
        {canUpload && (
          <div className="flex min-w-0 flex-col gap-1">
            <label htmlFor={`${id}-file`} className="text-sm">
              {upload.isPending ? t.field.uploading : slot.text ? t.field.replace : t.field.upload}
            </label>
            <Input
              id={`${id}-file`}
              type="file"
              accept={ACCEPTED_FILES}
              aria-describedby={hint}
              disabled={upload.isPending}
              onChange={(event) => {
                const file = event.target.files?.[0]
                if (file) upload.mutate(file)
                event.currentTarget.value = ''
              }}
            />
          </div>
        )}
        {(slot.text || slot.documentId) && (
          <Button
            type="button"
            variant="ghost"
            size="sm"
            onClick={() => {
              onChange(emptySlot(slot.title))
            }}
          >
            {t.field.clear}
          </Button>
        )}
      </div>
      {canUpload && (
        <p id={hint} className="text-xs text-muted-foreground">
          {t.field.formats}
        </p>
      )}
      {upload.error && (
        <p role="alert" className="text-sm text-destructive">
          {upload.error.message}
        </p>
      )}
    </div>
  )
}
