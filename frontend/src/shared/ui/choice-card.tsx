import type { ReactNode } from 'react'
import { cn } from 'cn'

import { RadioGroupItem } from './radio-group'

/**
 * One option of a radio group, drawn as a card. The title names the option; the description is
 * announced as its description. The whole card responds to the pointer.
 */
export function ChoiceCard({
  id,
  value,
  title,
  description,
  disabled,
  children,
  className,
}: {
  id: string
  value: string
  title: ReactNode
  description?: ReactNode
  disabled?: boolean
  children?: ReactNode
  className?: string
}) {
  const describedBy = description ? `${id}-description` : undefined
  return (
    <div
      className={cn(
        'relative flex gap-3 rounded-lg border p-3 transition-colors has-[[data-state=checked]]:border-brand has-[[data-state=checked]]:ring-1 has-[[data-state=checked]]:ring-brand',
        // No opacity or tinted background: the description keeps its contrast in every state.
        disabled ? 'border-dashed text-muted-foreground' : 'hover:border-foreground/40',
        className,
      )}
    >
      <RadioGroupItem
        id={id}
        value={value}
        disabled={disabled}
        aria-describedby={describedBy}
        className="relative z-10 mt-0.5"
      />
      <div className="flex min-w-0 flex-col gap-1">
        <label
          htmlFor={id}
          className={cn(
            'font-medium after:absolute after:inset-0',
            disabled ? 'cursor-not-allowed' : 'cursor-pointer',
          )}
        >
          {title}
        </label>
        {description && (
          <p id={describedBy} className="text-sm text-muted-foreground">
            {description}
          </p>
        )}
        {children && <div className="relative z-10">{children}</div>}
      </div>
    </div>
  )
}
