import { useEffect, useState } from 'react'

/** Samples `read` on every animation frame while `active`, for speaking animations. */
export function useAnimatedLevel(read: () => number, active: boolean): number {
  const [level, setLevel] = useState(0)
  useEffect(() => {
    if (!active) return
    let frame = 0
    const tick = () => {
      // Smooth a little so the rings do not flicker.
      setLevel((previous) => previous * 0.6 + read() * 0.4)
      frame = requestAnimationFrame(tick)
    }
    frame = requestAnimationFrame(tick)
    return () => {
      cancelAnimationFrame(frame)
    }
  }, [read, active])
  return active ? level : 0
}

/** Microphone dBFS mapped to 0..1 (-60 dBFS is silence, -10 dBFS is loud). */
export function micLevel(dbfs: number): number {
  if (!Number.isFinite(dbfs)) return 0
  return Math.min(1, Math.max(0, (dbfs + 60) / 50))
}
