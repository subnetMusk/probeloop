import { ArrowUpIcon } from 'lucide-react'
import { useEffect, useState } from 'react'
import type { RefObject } from 'react'
import { cn } from 'cn'

import { useMessages } from '@/shared/i18n'
import { shellMessages } from './messages'

const SHOW_AFTER = 320 // pixels scrolled before the button appears

/**
 * A round button, bottom right outside the page content, that scrolls back to the top. It
 * appears once the page has scrolled, and scrolls smoothly unless the user prefers less motion.
 */
export function BackToTop({ target }: { target: RefObject<HTMLElement | null> }) {
  const t = useMessages(shellMessages)
  const [visible, setVisible] = useState(false)
  useEffect(() => {
    const element = target.current
    if (!element) return
    const update = () => {
      setVisible(element.scrollTop > SHOW_AFTER)
    }
    update()
    element.addEventListener('scroll', update, { passive: true })
    return () => {
      element.removeEventListener('scroll', update)
    }
  }, [target])
  return (
    <button
      type="button"
      aria-label={t.backToTop}
      title={t.backToTop}
      data-testid="back-to-top"
      onClick={() => {
        const reduce = window.matchMedia('(prefers-reduced-motion: reduce)').matches
        target.current?.scrollTo({ top: 0, behavior: reduce ? 'auto' : 'smooth' })
      }}
      // In the gutter beside the 72rem content column when there is room; above the sticky
      // step bar on narrower windows.
      style={{ right: 'max(1.5rem, calc((100vw - 72rem) / 2 - 4.5rem))' }}
      className={cn(
        'fixed bottom-24 z-30 flex size-11 items-center justify-center rounded-full border bg-background text-foreground shadow-lg outline-none transition-all duration-200 hover:bg-muted focus-visible:ring-3 focus-visible:ring-ring/50 xl:bottom-8',
        visible ? 'visible translate-y-0 opacity-100' : 'invisible translate-y-2 opacity-0',
      )}
    >
      <ArrowUpIcon className="size-5" aria-hidden="true" />
    </button>
  )
}
