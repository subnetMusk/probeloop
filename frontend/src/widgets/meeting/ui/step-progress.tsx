import { CheckIcon, XIcon } from 'lucide-react'
import { useId } from 'react'

import { cn } from '@/shared/lib/utils'

export type StepMark = 'done' | 'active' | 'pending' | 'failed'

export interface RingSegment {
  name: string
  state: StepMark
  fill: number // 0..1
}

/** The state of one step: a check, a turning ring, a dot or a cross. */
export function StepIcon({ state, className }: { state: StepMark; className?: string }) {
  return (
    <span aria-hidden className={cn('flex size-4 shrink-0 items-center justify-center', className)}>
      {state === 'done' && <CheckIcon className="size-3.5 text-success" strokeWidth={3} />}
      {state === 'failed' && <XIcon className="size-3.5 text-red-400" strokeWidth={3} />}
      {state === 'active' && (
        <span className="size-3.5 rounded-full border-2 border-brand-text/25 border-t-brand-text motion-safe:animate-spin" />
      )}
      {state === 'pending' && <span className="size-1.5 rounded-full bg-zinc-600" />}
    </span>
  )
}

const CENTRE = 60
const RADIUS = 54
const GAP_DEG = 12

function point(angleDeg: number): [number, number] {
  const rad = (angleDeg * Math.PI) / 180
  return [CENTRE + RADIUS * Math.cos(rad), CENTRE + RADIUS * Math.sin(rad)]
}

function arc(fromDeg: number, toDeg: number): string {
  const [x1, y1] = point(fromDeg)
  const [x2, y2] = point(toDeg)
  const large = toDeg - fromDeg > 180 ? 1 : 0
  return `M ${x1.toFixed(2)} ${y1.toFixed(2)} A ${String(RADIUS)} ${String(RADIUS)} 0 ${String(large)} 1 ${x2.toFixed(2)} ${y2.toFixed(2)}`
}

/**
 * A ring of arcs around the interviewer's avatar, one arc per step, clockwise from the top. An
 * arc fills with the brand gradient as its step runs, and a glowing point leads the running one.
 */
export function ProgressRing({
  segments,
  dimmed = false,
  className,
}: {
  segments: RingSegment[]
  dimmed?: boolean // after a failure: only the failed arcs keep their colour
  className?: string
}) {
  const id = useId()
  const gradient = `${id}-gradient`
  const glow = `${id}-glow`
  const gap = segments.length > 1 ? GAP_DEG : 0
  const span = 360 / Math.max(1, segments.length) - gap
  return (
    <svg viewBox="0 0 120 120" aria-hidden className={cn('pointer-events-none', className)}>
      <defs>
        <linearGradient
          id={gradient}
          gradientUnits="userSpaceOnUse"
          x1="0"
          y1="0"
          x2="120"
          y2="120"
        >
          <stop offset="0%" style={{ stopColor: 'var(--brand)' }} />
          <stop offset="100%" style={{ stopColor: 'var(--highlight)' }} />
        </linearGradient>
        <filter id={glow} x="-100%" y="-100%" width="300%" height="300%">
          <feGaussianBlur stdDeviation="2.4" />
        </filter>
      </defs>
      {segments.map((segment, i) => {
        const start = -90 + gap / 2 + i * (span + gap)
        const path = arc(start, start + span)
        const fill = Math.min(1, Math.max(0, segment.fill))
        let stroke = `url(#${gradient})`
        if (segment.state === 'failed') stroke = 'rgb(248 113 113)'
        else if (dimmed) stroke = 'rgb(255 255 255 / 0.22)'
        return (
          <g key={segment.name} data-segment={segment.name} data-state={segment.state}>
            <path
              d={path}
              pathLength={100}
              fill="none"
              stroke="rgb(255 255 255 / 0.09)"
              strokeWidth={3}
              strokeLinecap="round"
            />
            {fill > 0.005 && (
              <path
                d={path}
                pathLength={100}
                fill="none"
                stroke={stroke}
                strokeWidth={3}
                strokeLinecap="round"
                strokeDasharray={`${(fill * 100).toFixed(2)} 100`}
                className="motion-safe:transition-[stroke-dasharray] motion-safe:duration-500 motion-safe:ease-out"
              />
            )}
            {segment.state === 'active' && (
              <g
                className="motion-safe:transition-transform motion-safe:duration-500 motion-safe:ease-out"
                style={{
                  transform: `rotate(${(start + 90 + span * fill).toFixed(2)}deg)`,
                  transformOrigin: `${String(CENTRE)}px ${String(CENTRE)}px`,
                }}
              >
                <circle
                  cx={CENTRE}
                  cy={CENTRE - RADIUS}
                  r={4.5}
                  fill="var(--highlight)"
                  filter={`url(#${glow})`}
                  className="motion-safe:animate-pulse"
                />
                <circle cx={CENTRE} cy={CENTRE - RADIUS} r={2} fill="white" />
              </g>
            )}
          </g>
        )
      })}
    </svg>
  )
}
