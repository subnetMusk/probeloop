import { Progress } from '@/components/ui/progress'

/** Microphone level, from -60 dBFS (empty) to 0 dBFS (full). */
export function LevelMeter({ dbfs, label }: { dbfs: number; label?: string }) {
  const value = Number.isFinite(dbfs) ? Math.min(100, Math.max(0, ((dbfs + 60) / 60) * 100)) : 0
  return (
    <div className="flex flex-col gap-1.5">
      <Progress value={value} aria-label={label ?? 'Microphone level'} data-testid="level-meter" />
      <span className="text-xs text-muted-foreground">
        {Number.isFinite(dbfs) ? `${dbfs.toFixed(0)} dBFS` : 'silence'}
      </span>
    </div>
  )
}
