import { ArrowUpIcon } from 'lucide-react'
import { useEffect, useState } from 'react'
import type { RefObject } from 'react'
import { cn } from 'cn'

import { useMessages } from '@/shared/i18n'
import { shellMessages } from './messages'

const LONG_PAGE_SCREENS = 3 // shorter pages scroll back easily without it
const DIRECTION_SLOP = 8 // pixels before a scroll counts as a change of direction

/**
 * "Back to top", following NN/g's guidelines: only on long pages, after the first screen, when
 * the reader scrolls back up or reaches the end; bottom right, small and still.
 *
 * It sits in a zero-height sticky row between the page and the footer. While the page scrolls
 * the row sticks to the bottom of the content area; once the footer comes into view it rests
 * above it, inside the page's bottom padding, so it never covers the footer or the content end.
 * Wide windows place it in the gutter beside the content column.
 */
export function BackToTop({ target }: { target: RefObject<HTMLElement | null> }) {
  const t = useMessages(shellMessages)
  const [visible, setVisible] = useState(false)
  useEffect(() => {
    const element = target.current
    if (!element) return
    let last = element.scrollTop
    let upwards = false
    const update = () => {
      const { scrollTop, scrollHeight, clientHeight } = element
      if (Math.abs(scrollTop - last) > DIRECTION_SLOP) {
        upwards = scrollTop < last
        last = scrollTop
      }
      const long = scrollHeight > clientHeight * LONG_PAGE_SCREENS
      const atEnd = scrollTop + clientHeight >= scrollHeight - clientHeight / 2
      // Pages with their own sticky action bar (the interview wizard) keep that corner free.
      const ownBar = element.querySelector('[data-sticky-bar]') !== null
      setVisible(long && !ownBar && scrollTop > clientHeight && (upwards || atEnd))
    }
    update()
    element.addEventListener('scroll', update, { passive: true })
    return () => {
      element.removeEventListener('scroll', update)
    }
  }, [target])
  return (
    <div className="pointer-events-none sticky bottom-0 z-30 h-0">
      <div className="relative mx-auto h-0 w-full max-w-6xl">
        <button
          type="button"
          data-testid="back-to-top"
          aria-label={t.backToTop}
          tabIndex={visible ? 0 : -1}
          aria-hidden={!visible}
          onClick={() => {
            const reduce = window.matchMedia('(prefers-reduced-motion: reduce)').matches
            target.current?.scrollTo({ top: 0, behavior: reduce ? 'auto' : 'smooth' })
            // Keyboard users continue from the top of the page, not from the button.
            const start =
              target.current?.querySelector<HTMLElement>('h1') ??
              target.current?.querySelector<HTMLElement>('main')
            if (start) {
              if (!start.hasAttribute('tabindex')) start.tabIndex = -1
              start.focus({ preventScroll: true })
            }
          }}
          className={cn(
            'absolute right-4 bottom-3 flex size-10 shrink-0 items-center justify-center rounded-full border bg-card text-foreground shadow-md outline-none transition-[opacity,transform] duration-200 hover:bg-muted focus-visible:ring-3 focus-visible:ring-ring/50 motion-reduce:transition-none sm:right-6 2xl:right-auto 2xl:left-[calc(100%+1rem)]',
            visible
              ? 'pointer-events-auto translate-y-0 opacity-100'
              : 'pointer-events-none translate-y-1 opacity-0',
          )}
        >
          <ArrowUpIcon className="size-4" aria-hidden="true" />
        </button>
      </div>
    </div>
  )
}
