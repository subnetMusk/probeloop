import type { ReactNode } from 'react'
import { ArrowDownRightIcon, ArrowUpRightIcon } from 'lucide-react'
import { cn } from 'cn'

/**
 * One headline number: a label, the value, and an optional change or note. Up is good for every
 * value shown here, so a positive change reads as an improvement.
 */
export function StatTile({
  label,
  value,
  unit,
  delta,
  deltaLabel,
  note,
  icon,
}: {
  label: string
  value: ReactNode
  unit?: string
  /** Signed change, already formatted ("+0.4"), with its direction. */
  delta?: { text: string; direction: 'up' | 'down' | 'flat' }
  /** What the change compares with, for assistive technologies and the tooltip. */
  deltaLabel?: string
  note?: ReactNode
  icon?: ReactNode
}) {
  return (
    <div className="flex flex-col gap-2 rounded-xl p-4 ring-1 ring-foreground/10">
      <div className="flex items-center justify-between gap-2 text-sm text-muted-foreground">
        <span>{label}</span>
        {icon && <span aria-hidden="true">{icon}</span>}
      </div>
      <div className="flex flex-wrap items-baseline gap-x-2 gap-y-1">
        <span className="font-heading text-3xl font-semibold tracking-tight">{value}</span>
        {unit && <span className="text-sm text-muted-foreground">{unit}</span>}
        {delta && (
          <span
            title={deltaLabel}
            className={cn(
              'inline-flex items-center gap-0.5 text-xs font-medium',
              delta.direction === 'up' && 'text-success',
              delta.direction === 'down' && 'text-warning',
              delta.direction === 'flat' && 'text-muted-foreground',
            )}
          >
            {delta.direction === 'up' && <ArrowUpRightIcon className="size-3.5" aria-hidden="true" />}
            {delta.direction === 'down' && (
              <ArrowDownRightIcon className="size-3.5" aria-hidden="true" />
            )}
            {delta.text}
            {deltaLabel && <span className="sr-only"> {deltaLabel}</span>}
          </span>
        )}
      </div>
      {note && <p className="text-xs text-muted-foreground">{note}</p>}
    </div>
  )
}
