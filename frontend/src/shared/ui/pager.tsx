import { ChevronLeftIcon, ChevronRightIcon } from 'lucide-react'

import { defineMessages, useMessages } from '@/shared/i18n'
import { Button } from './button'

const messages = defineMessages({
  en: {
    previous: 'Previous page',
    next: 'Next page',
    position: (page: number, pages: number) => `${String(page)} of ${String(pages)}`,
  },
  it: {
    previous: 'Pagina precedente',
    next: 'Pagina successiva',
    position: (page: number, pages: number) => `${String(page)} di ${String(pages)}`,
  },
})

/** Previous and next page of a short list; hidden when everything fits on one page. */
export function Pager({
  label,
  page,
  pages,
  onPage,
}: {
  /** What is paged, for assistive technologies ("Recent interviews"). */
  label: string
  page: number
  pages: number
  onPage: (page: number) => void
}) {
  const t = useMessages(messages)
  if (pages <= 1) return null
  return (
    <nav aria-label={label} className="flex items-center justify-end gap-1 text-sm">
      <Button
        type="button"
        variant="ghost"
        size="icon-sm"
        aria-label={t.previous}
        disabled={page === 0}
        onClick={() => {
          onPage(page - 1)
        }}
      >
        <ChevronLeftIcon />
      </Button>
      <span className="min-w-14 text-center text-muted-foreground tabular-nums" aria-live="polite">
        {t.position(page + 1, pages)}
      </span>
      <Button
        type="button"
        variant="ghost"
        size="icon-sm"
        aria-label={t.next}
        disabled={page >= pages - 1}
        onClick={() => {
          onPage(page + 1)
        }}
      >
        <ChevronRightIcon />
      </Button>
    </nav>
  )
}
