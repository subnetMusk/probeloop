import { cn } from '@/shared/lib/utils'

/** The typographic logo: "ProbeLoop" in the heading font, with "Loop" in the accent colour. */
export function Wordmark({ className }: { className?: string }) {
  return (
    <span className={cn('font-heading text-xl font-bold tracking-tight', className)}>
      Probe<span className="text-brand-text">Loop</span>
    </span>
  )
}
