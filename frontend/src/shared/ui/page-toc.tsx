import { useEffect, useRef, useState } from 'react'
import type { ReactNode } from 'react'

import { cn } from '@/shared/lib/utils'

export interface TocItem {
  id: string // the id of the section's element
  label: string
}

function scrollParent(element: HTMLElement | null): HTMLElement | Window {
  for (let node = element?.parentElement; node; node = node.parentElement) {
    const { overflowY } = getComputedStyle(node)
    if (overflowY === 'auto' || overflowY === 'scroll') return node
  }
  return window
}

function readingTop(root: HTMLElement | Window): number {
  const top = root instanceof Window ? 0 : root.getBoundingClientRect().top
  const header = document.querySelector('[data-app-header]')
  return Math.max(0, top, header?.getBoundingClientRect().bottom ?? 0)
}

function sectionMargin(element: HTMLElement): number {
  return Number.parseFloat(getComputedStyle(element).scrollMarginTop) || 0
}

function goTo(id: string) {
  const target = document.getElementById(id)
  if (!target) return
  const reduce = window.matchMedia('(prefers-reduced-motion: reduce)').matches
  const root = scrollParent(target)
  const scrollTop = root instanceof Window ? window.scrollY : root.scrollTop
  root.scrollTo({
    top: scrollTop + target.getBoundingClientRect().top - readingTop(root) - sectionMargin(target),
    behavior: reduce ? 'auto' : 'smooth',
  })
  history.replaceState(null, '', `#${id}`)
  // Keyboard and screen-reader users continue from the section they chose.
  if (!target.hasAttribute('tabindex')) target.setAttribute('tabindex', '-1')
  target.focus({ preventScroll: true })
}

/** The section currently read: the last one whose top has passed the top of the scroll area. */
function useCurrentSection(ids: string[], anchor: React.RefObject<HTMLElement | null>) {
  const [current, setCurrent] = useState(ids[0])
  const chosen = useRef<string | null>(null)
  const key = ids.join(' ')
  useEffect(() => {
    const root = scrollParent(anchor.current)
    chosen.current = null
    const update = () => {
      // A chosen short section may not reach the reading line at the end of the page.
      // Keep that choice through smooth scrolling until the reader scrolls again.
      if (chosen.current) return
      const top = readingTop(root)
      const scrollTop = root instanceof Window ? window.scrollY : root.scrollTop
      const height = root instanceof Window ? window.innerHeight : root.clientHeight
      const scrollHeight =
        root instanceof Window ? document.documentElement.scrollHeight : root.scrollHeight
      const maximum = scrollHeight - height
      const sections = ids.flatMap((id) => {
        const element = document.getElementById(id)
        return element
          ? [
              {
                id,
                start:
                  scrollTop + element.getBoundingClientRect().top - top - sectionMargin(element),
              },
            ]
          : []
      })
      const last = sections.at(-1)?.start ?? 0
      // Short trailing sections cannot all reach the top. Spread their activation points
      // over the final half viewport instead of jumping straight to the last at the end.
      const compressFrom = Math.max(0, maximum - height / 2)
      let found = ids[0]
      for (const section of sections) {
        const start =
          maximum > 0 && last > maximum && section.start > compressFrom
            ? compressFrom +
              ((section.start - compressFrom) * (maximum - compressFrom)) / (last - compressFrom)
            : section.start
        if (start <= scrollTop + 1) found = section.id
      }
      setCurrent(found)
    }
    const resume = () => {
      chosen.current = null
    }
    const finishScroll = () => {
      const section = chosen.current ? document.getElementById(chosen.current) : null
      if (!section) return
      const scrollTop = root instanceof Window ? window.scrollY : root.scrollTop
      const maximum =
        root instanceof Window
          ? document.documentElement.scrollHeight - window.innerHeight
          : root.scrollHeight - root.clientHeight
      const destination = Math.max(
        0,
        Math.min(
          maximum,
          scrollTop +
            section.getBoundingClientRect().top -
            readingTop(root) -
            sectionMargin(section),
        ),
      )
      // Another control can scroll the page too, including keyboard activation of Back to top.
      if (Math.abs(scrollTop - destination) > 2) {
        resume()
        update()
      }
    }
    const keyboard = (event: Event) => {
      if (
        event instanceof KeyboardEvent &&
        ['ArrowUp', 'ArrowDown', 'PageUp', 'PageDown', 'Home', 'End', ' '].includes(event.key)
      )
        resume()
    }
    update()
    root.addEventListener('scroll', update, { passive: true })
    root.addEventListener('scrollend', finishScroll)
    root.addEventListener('wheel', resume, { passive: true })
    root.addEventListener('touchstart', resume, { passive: true })
    root.addEventListener('pointerdown', resume, { passive: true })
    root.addEventListener('keydown', keyboard)
    window.addEventListener('resize', update)
    const observer = typeof ResizeObserver === 'undefined' ? null : new ResizeObserver(update)
    if (root instanceof HTMLElement) observer?.observe(root)
    for (const id of ids) {
      const section = document.getElementById(id)
      if (section) observer?.observe(section)
    }
    return () => {
      root.removeEventListener('scroll', update)
      root.removeEventListener('scrollend', finishScroll)
      root.removeEventListener('wheel', resume)
      root.removeEventListener('touchstart', resume)
      root.removeEventListener('pointerdown', resume)
      root.removeEventListener('keydown', keyboard)
      window.removeEventListener('resize', update)
      observer?.disconnect()
    }
    // `key` stands for the ids.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key, anchor])
  return {
    current,
    navigate: (id: string) => {
      chosen.current = id
      setCurrent(id)
      goTo(id)
    },
  }
}

function headingOf(section: HTMLElement): string {
  const labelled = section.getAttribute('aria-labelledby')
  const heading = labelled ? document.getElementById(labelled) : section.querySelector('h2')
  return (heading?.textContent ?? section.getAttribute('aria-label') ?? '').trim()
}

/** The `section[id]` elements of the content that have a heading, as they appear. */
function useDiscoveredSections(content: React.RefObject<HTMLDivElement | null>, enabled: boolean) {
  const [items, setItems] = useState<TocItem[]>([])
  useEffect(() => {
    const root = content.current
    if (!enabled || !root) return
    const scan = () => {
      const found = Array.from(root.querySelectorAll<HTMLElement>('section[id]'))
        // Nested sections stay inside their parent's entry.
        .filter((section) => section.parentElement?.closest('section[id]') === null)
        .map((section) => ({ id: section.id, label: headingOf(section) }))
        .filter((item) => item.label)
      setItems((previous) =>
        JSON.stringify(previous) === JSON.stringify(found) ? previous : found,
      )
    }
    const frame = requestAnimationFrame(scan)
    const observer = new MutationObserver(scan)
    observer.observe(root, { childList: true, subtree: true })
    return () => {
      cancelAnimationFrame(frame)
      observer.disconnect()
    }
  }, [content, enabled])
  return items
}

/**
 * A page with an "On this page" table of contents (NN/g): a sticky left rail on wide windows
 * that highlights the section being read, and a plain list above the content on narrow ones.
 * Without `items`, the entries are the content's top-level `section[id]` elements and their
 * headings, found as the content renders.
 */
export function TocLayout({
  label,
  items: given,
  children,
}: {
  label: string
  items?: TocItem[]
  children: ReactNode
}) {
  const anchor = useRef<HTMLDivElement>(null)
  const content = useRef<HTMLDivElement>(null)
  const discovered = useDiscoveredSections(content, given === undefined)
  const items = given ?? discovered
  const { current, navigate } = useCurrentSection(
    items.map((item) => item.id),
    anchor,
  )
  const links = (compact: boolean) => (
    <ul className={cn('flex flex-col', compact ? 'gap-1' : 'gap-0.5 border-l')}>
      {items.map((item) => {
        const active = item.id === current
        return (
          <li key={item.id}>
            <a
              href={`#${item.id}`}
              aria-current={active ? 'location' : undefined}
              onClick={(event) => {
                event.preventDefault()
                navigate(item.id)
              }}
              className={cn(
                'block text-sm outline-none transition-colors focus-visible:ring-3 focus-visible:ring-ring/50',
                compact
                  ? 'rounded-sm py-1 text-brand-text underline-offset-4 hover:underline'
                  : // A straight marker on the rail's line, never a rounded bracket.
                    '-ml-px rounded-none border-l-2 py-1.5 pl-3',
                compact && active && 'font-semibold',
                !compact &&
                  (active
                    ? 'border-brand font-medium text-foreground'
                    : 'border-transparent text-muted-foreground hover:border-border hover:text-foreground'),
              )}
            >
              {item.label}
            </a>
          </li>
        )
      })}
    </ul>
  )
  return (
    <div
      ref={anchor}
      className="grid gap-8 lg:grid-cols-[12.5rem_minmax(0,1fr)] lg:gap-10"
      data-testid="toc-layout"
    >
      <nav aria-label={label} className="hidden lg:block">
        <div className="sticky top-6">
          <p className="mb-3 text-xs font-semibold tracking-wide text-muted-foreground uppercase">
            {label}
          </p>
          {links(false)}
        </div>
      </nav>
      <details className="rounded-xl border bg-card px-4 py-3 lg:hidden">
        <summary className="cursor-pointer text-sm font-semibold">{label}</summary>
        <nav aria-label={label} className="mt-2">
          {links(true)}
        </nav>
      </details>
      <div ref={content} className="flex min-w-0 flex-col gap-8">
        {children}
      </div>
    </div>
  )
}
