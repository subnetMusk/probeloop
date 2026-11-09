import { useLayoutEffect, useMemo, useRef, useState } from 'react'
import type { ReactNode } from 'react'

export interface ChartPoint {
  id: string
  /** Epoch seconds. */
  x: number
  y: number
  /** The first line of the tooltip and the table's first column, such as the date. */
  title: string
  /** A secondary line, such as who scored it. */
  detail?: string
  /** Opens the point, for example its report. */
  onSelect?: () => void
  /** The same action as a link, for the table view. */
  link?: ReactNode
}

export interface ChartSeries {
  id: string
  name: string
  /** A CSS colour, such as `var(--chart-1)`. */
  color: string
  /** Runs of points joined by a line; a new run starts where they are not comparable. */
  segments: ChartPoint[][]
}

const MARGIN = { top: 12, right: 16, bottom: 28, left: 28 }
const HIT_RADIUS = 28

/** Up to four ticks across the points, one per distinct label, so a single day shows once. */
function ticksBetween(min: number, max: number, label: (x: number) => string): number[] {
  if (min === max) return [min]
  const seen = new Set<string>()
  const ticks = Array.from({ length: 4 }, (_, i) => min + ((max - min) * i) / 3).filter((x) => {
    const text = label(x)
    if (seen.has(text)) return false
    seen.add(text)
    return true
  })
  return ticks.length === 1 ? [(min + max) / 2] : ticks
}

/**
 * Scores over time on a fixed 1 to 5 scale. Lines are 2 px, points have a ring in the surface
 * colour, and a crosshair with a tooltip follows the pointer to the nearest point. Every value
 * is also in the table view, so the tooltip never gates information.
 */
export function TrendChart({
  series,
  ariaLabel,
  formatX,
  formatY,
  table,
  height = 220,
}: {
  series: ChartSeries[]
  ariaLabel: string
  formatX: (x: number) => string
  formatY: (y: number) => string
  table: { summary: string; date: string; series: string; value: string; open: string }
  height?: number
}) {
  const box = useRef<HTMLDivElement>(null)
  const [width, setWidth] = useState(640)
  const [active, setActive] = useState<{ point: ChartPoint; series: ChartSeries } | null>(null)
  useLayoutEffect(() => {
    const element = box.current
    if (!element) return
    const observer = new ResizeObserver(([entry]) => {
      if (entry) setWidth(Math.max(240, Math.round(entry.contentRect.width)))
    })
    observer.observe(element)
    return () => {
      observer.disconnect()
    }
  }, [])

  const points = useMemo(
    () => series.flatMap((s) => s.segments.flat().map((point) => ({ point, series: s }))),
    [series],
  )
  const xs = points.map((p) => p.point.x)
  const minX = xs.length ? Math.min(...xs) : 0
  const maxX = xs.length ? Math.max(...xs) : 1
  // Room on both sides, so that no point sits on the edge of the plot.
  const pad = Math.max((maxX - minX) * 0.06, 6 * 3600)
  const [x0, x1] = [minX - pad, maxX + pad]
  const plotW = width - MARGIN.left - MARGIN.right
  const plotH = height - MARGIN.top - MARGIN.bottom
  const sx = (x: number) => MARGIN.left + ((x - x0) / (x1 - x0)) * plotW
  const sy = (y: number) => MARGIN.top + ((5 - y) / 4) * plotH
  const xTicks = ticksBetween(minX, maxX, formatX)

  const nearest = (clientX: number, clientY: number, rect: DOMRect) => {
    const px = clientX - rect.left
    const py = clientY - rect.top
    let best: (typeof points)[number] | null = null
    let distance = HIT_RADIUS
    for (const candidate of points) {
      const d = Math.hypot(sx(candidate.point.x) - px, sy(candidate.point.y) - py)
      if (d <= distance) {
        best = candidate
        distance = d
      }
    }
    return best
  }

  const rows = [...points].sort((a, b) => b.point.x - a.point.x)
  return (
    <div className="flex flex-col gap-3">
      {series.length > 1 && (
        <ul className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-muted-foreground">
          {series.map((s) => (
            <li key={s.id} className="flex items-center gap-1.5">
              <span
                aria-hidden="true"
                className="h-0.5 w-3.5 rounded-full"
                style={{ backgroundColor: s.color }}
              />
              {s.name}
            </li>
          ))}
        </ul>
      )}
      <div ref={box} className="relative w-full" style={{ height }}>
        <svg
          role="img"
          aria-label={ariaLabel}
          width={width}
          height={height}
          className={active?.point.onSelect ? 'cursor-pointer' : undefined}
          onPointerMove={(event) => {
            setActive(
              nearest(event.clientX, event.clientY, event.currentTarget.getBoundingClientRect()),
            )
          }}
          onPointerLeave={() => {
            setActive(null)
          }}
          onClick={() => {
            active?.point.onSelect?.()
          }}
        >
          {[1, 2, 3, 4, 5].map((tick) => (
            <g key={tick}>
              <line
                x1={MARGIN.left}
                x2={width - MARGIN.right}
                y1={sy(tick)}
                y2={sy(tick)}
                stroke="var(--border)"
                strokeWidth={1}
              />
              <text
                x={MARGIN.left - 10}
                y={sy(tick)}
                dy="0.32em"
                textAnchor="end"
                className="fill-muted-foreground text-[11px] tabular-nums"
              >
                {tick}
              </text>
            </g>
          ))}
          {points.length > 0 &&
            xTicks.map((tick) => (
              <text
                key={tick}
                x={sx(tick)}
                y={height - 8}
                textAnchor={
                  xTicks.length > 1 && sx(tick) < MARGIN.left + 40
                    ? 'start'
                    : xTicks.length > 1 && sx(tick) > width - MARGIN.right - 40
                      ? 'end'
                      : 'middle'
                }
                className="fill-muted-foreground text-[11px]"
              >
                {formatX(tick)}
              </text>
            ))}
          {active && (
            <line
              x1={sx(active.point.x)}
              x2={sx(active.point.x)}
              y1={MARGIN.top}
              y2={height - MARGIN.bottom}
              stroke="var(--muted-foreground)"
              strokeWidth={1}
              opacity={0.5}
            />
          )}
          {series.map((s) =>
            s.segments
              .filter((segment) => segment.length > 1)
              .map((segment) => (
                <polyline
                  key={`${s.id}-${segment[0]?.id ?? ''}`}
                  points={segment.map((p) => `${String(sx(p.x))},${String(sy(p.y))}`).join(' ')}
                  fill="none"
                  stroke={s.color}
                  strokeWidth={2}
                  strokeLinejoin="round"
                  strokeLinecap="round"
                />
              )),
          )}
          {points.map(({ point, series: s }) => (
            <circle
              key={`${s.id}-${point.id}`}
              cx={sx(point.x)}
              cy={sy(point.y)}
              r={active?.point === point ? 6 : 4}
              fill={s.color}
              stroke="var(--card)"
              strokeWidth={2}
            />
          ))}
        </svg>
        {active && (
          <div
            aria-hidden="true"
            className="pointer-events-none absolute z-10 min-w-36 -translate-x-1/2 -translate-y-full rounded-lg border bg-popover px-3 py-2 text-xs text-popover-foreground shadow-md"
            style={{
              left: Math.min(Math.max(sx(active.point.x), 72), width - 72),
              top: sy(active.point.y) - 10,
            }}
          >
            <p className="font-heading text-base font-semibold">{formatY(active.point.y)}</p>
            {series.length > 1 && (
              <p className="flex items-center gap-1.5 text-muted-foreground">
                <span
                  className="h-0.5 w-3 rounded-full"
                  style={{ backgroundColor: active.series.color }}
                />
                {active.series.name}
              </p>
            )}
            <p>{active.point.title}</p>
            {active.point.detail && (
              <p className="text-muted-foreground">{active.point.detail}</p>
            )}
          </div>
        )}
      </div>
      <details className="text-sm">
        <summary className="cursor-pointer text-muted-foreground hover:text-foreground">
          {table.summary}
        </summary>
        <div className="mt-2 max-h-64 overflow-y-auto">
          <table className="w-full text-left">
            <thead className="text-xs text-muted-foreground">
              <tr>
                <th className="py-1 pr-3 font-medium">{table.date}</th>
                {series.length > 1 && <th className="py-1 pr-3 font-medium">{table.series}</th>}
                <th className="py-1 pr-3 font-medium">{table.value}</th>
                <th className="py-1 font-medium">
                  <span className="sr-only">{table.open}</span>
                </th>
              </tr>
            </thead>
            <tbody>
              {rows.map(({ point, series: s }) => (
                <tr key={`${s.id}-${point.id}`} className="border-t">
                  <td className="py-1.5 pr-3">{point.title}</td>
                  {series.length > 1 && <td className="py-1.5 pr-3">{s.name}</td>}
                  <td className="py-1.5 pr-3 tabular-nums">{formatY(point.y)}</td>
                  <td className="py-1.5">{point.link}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </details>
    </div>
  )
}
