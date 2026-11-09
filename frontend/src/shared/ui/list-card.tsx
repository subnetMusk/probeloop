import type { ReactNode } from 'react'

import { Card, CardContent, CardHeader, CardTitle } from './card'

/** A titled card holding a short list, an optional link to the full list and a pager. */
export function ListCard({
  title,
  action,
  toolbar,
  children,
  footer,
}: {
  title: string
  /** A link to the full list, beside the title. */
  action?: ReactNode
  /** Filters, below the title. */
  toolbar?: ReactNode
  children: ReactNode
  footer?: ReactNode
}) {
  return (
    <Card className="gap-2">
      <CardHeader className="flex flex-col gap-3">
        <div className="flex items-center justify-between gap-3">
          <CardTitle role="heading" aria-level={2}>
            {title}
          </CardTitle>
          {action}
        </div>
        {toolbar}
      </CardHeader>
      <CardContent className="flex flex-col gap-2">
        {children}
        {footer}
      </CardContent>
    </Card>
  )
}

/** A row of toggle buttons that narrows a list or a chart. */
export function FilterPills({
  label,
  options,
  value,
  onChange,
}: {
  label: string
  options: readonly { value: string; label: string }[]
  value: string
  onChange: (value: string) => void
}) {
  return (
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
}
