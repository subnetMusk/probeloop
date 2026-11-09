import { cn } from 'cn'

import { score } from '@/shared/lib/format'
import { useLanguage } from '@/shared/lib/preferences'

/**
 * An overall score out of 5. The number carries the meaning; the ring only groups the value
 * visually. Scores describe practice evidence, never a hiring prediction.
 */
export function ScoreBadge({
  value,
  missing,
  size = 'md',
  className,
}: {
  value: number | null
  /** What to say when there is no score, for example "no report". */
  missing: string
  size?: 'md' | 'lg'
  className?: string
}) {
  const language = useLanguage()
  if (value === null)
    return <span className={cn('text-sm text-muted-foreground', className)}>{missing}</span>
  return (
    <span
      className={cn(
        'inline-flex items-baseline gap-0.5 rounded-full border px-2 py-0.5 font-heading font-semibold',
        size === 'lg' ? 'text-2xl' : 'text-sm',
        className,
      )}
    >
      {score(value, language)}
      <span className="text-xs font-normal text-muted-foreground">/5</span>
    </span>
  )
}
