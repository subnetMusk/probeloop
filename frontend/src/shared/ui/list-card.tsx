import type { ReactNode } from 'react'

import { Card, CardContent, CardHeader, CardTitle } from './card'

/** Every list row has this height, so lists side by side line up row by row. */
export const ROW_HEIGHT = 'h-14'
const ROW_REM = 3.5

/**
 * A titled card holding a short list, an optional link to the full list and a pager. The card
 * fills its grid cell, the list keeps room for a whole page, and the pager sits at the bottom, so
 * cards in one row have the same height and their pagers line up.
 */
export function ListCard({
  title,
  action,
  toolbar,
  rows,
  children,
  footer,
}: {
  title: string
  /** A link to the full list, beside the title. */
  action?: ReactNode
  /** Filters, below the title. */
  toolbar?: ReactNode
  /** The page size: the list keeps room for this many rows. */
  rows?: number
  children: ReactNode
  footer?: ReactNode
}) {
  return (
    <Card className="h-full gap-3">
      <CardHeader className="flex flex-col gap-3">
        <div className="flex min-h-7 items-center justify-between gap-3">
          <CardTitle role="heading" aria-level={2}>
            {title}
          </CardTitle>
          {action}
        </div>
        {toolbar}
      </CardHeader>
      <CardContent className="flex flex-1 flex-col gap-2">
        <div
          className="flex flex-1 flex-col"
          style={rows ? { minHeight: `${String(rows * ROW_REM)}rem` } : undefined}
        >
          {children}
        </div>
        {footer && <div className="mt-auto min-h-8">{footer}</div>}
      </CardContent>
    </Card>
  )
}

/** The message of an empty list, centred in the room the list keeps. */
export function ListEmpty({ children }: { children: ReactNode }) {
  return (
    <div className="flex flex-1 items-center justify-center px-2 py-6 text-center text-sm text-muted-foreground">
      <p>{children}</p>
    </div>
  )
}

/** A row of toggle buttons that narrows a list or a chart. */
export function FilterPills({
  label,
  options,
  value,
  onChange,
  showLabel = false,
}: {
  label: string
  options: readonly { value: string; label: string }[]
  value: string
  onChange: (value: string) => void
  /** Print the group's name before the pills, when several groups share option names. */
  showLabel?: boolean
}) {
  const pills = (
    <div role="group" aria-label={label} className="flex flex-wrap gap-1 self-start rounded-lg bg-muted p-1 text-xs">
      {options.map((option) => (
        <button
          key={option.value}
          type="button"
          aria-pressed={value === option.value}
          onClick={() => {
            onChange(option.value)
          }}
          className={
            value === option.value
              ? 'rounded-md bg-background px-2.5 py-1 font-medium text-foreground shadow-sm'
              : // Muted text would fall below 4.5:1 on the muted track.
                'rounded-md px-2.5 py-1 font-medium text-foreground/75 hover:text-foreground'
          }
        >
          {option.label}
        </button>
      ))}
    </div>
  )
  if (!showLabel) return pills
  return (
    <div className="flex items-center gap-2">
      <span aria-hidden="true" className="text-xs font-medium text-muted-foreground">
        {label}
      </span>
      {pills}
    </div>
  )
}
