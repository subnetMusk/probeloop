import type { ReactNode } from 'react'
import { cn } from 'cn'

/** The type of a page title, for titles that render their own `h1` (a renamable name). */
export const PAGE_TITLE = 'font-heading text-4xl font-bold tracking-tight text-balance sm:text-5xl'

/**
 * The top of a page: an optional eyebrow, the title, a short description and the page actions.
 * Every page uses it, so titles have the same weight and the same place everywhere.
 */
export function PageHeader({
  eyebrow,
  title,
  description,
  actions,
  children,
}: {
  eyebrow?: ReactNode
  /** Text becomes the `h1`; an element is used as it is and must contain the `h1`. */
  title: ReactNode
  description?: ReactNode
  actions?: ReactNode
  children?: ReactNode
}) {
  return (
    <header className="flex flex-wrap items-end justify-between gap-x-6 gap-y-4">
      <div className="flex min-w-0 flex-1 flex-col gap-2">
        {eyebrow && (
          <p className="text-xs font-semibold tracking-widest text-brand-text uppercase">
            {eyebrow}
          </p>
        )}
        {typeof title === 'string' ? <h1 className={PAGE_TITLE}>{title}</h1> : title}
        {description && <p className="max-w-2xl text-muted-foreground">{description}</p>}
        {children}
      </div>
      {actions && <div className="flex shrink-0 flex-wrap items-center gap-2">{actions}</div>}
    </header>
  )
}

/**
 * The content column of a page, aligned with the navigation. `narrow` keeps text pages at a
 * reading width without moving their left edge.
 */
export function Page({
  children,
  narrow = false,
  className,
}: {
  children: ReactNode
  narrow?: boolean
  className?: string
}) {
  return (
    <main className={cn('mx-auto flex w-full max-w-6xl flex-col gap-8 px-6 pt-6 pb-12', className)}>
      {narrow ? <div className="flex max-w-3xl flex-col gap-8">{children}</div> : children}
    </main>
  )
}
