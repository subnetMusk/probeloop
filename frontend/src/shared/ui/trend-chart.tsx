import { useId, useLayoutEffect, useMemo, useRef, useState } from 'react'
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
  /**
   * Something to know when comparing this point with the previous one, such as a change of
   * evaluator. The point is drawn hollow, and the note is in the tooltip and the table.
   */
  note?: string
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

const MARGIN = { top: 14, right: 40, bottom: 28, left: 36 }
const Y_TICKS = [0, 25, 50, 75, 100]

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
 * A monotone cubic path through the points (Fritsch-Carlson): smooth, but never above or below
 * the values it joins, so the curve does not invent peaks between two reports.
 */
export function monotonePath(points: readonly (readonly [number, number])[]): string {
  const n = points.length
  if (n === 0) return ''
  const [first] = points
  if (!first) return ''
  if (n < 3) return points.map(([x, y], i) => `${i ? 'L' : 'M'}${String(x)},${String(y)}`).join('')
  const dx: number[] = []
  const slope: number[] = []
  for (let i = 0; i < n - 1; i++) {
    const [x0, y0] = points[i] ?? first
    const [x1, y1] = points[i + 1] ?? first
    dx.push(x1 - x0)
    slope.push(x1 === x0 ? 0 : (y1 - y0) / (x1 - x0))
  }
  // Steffen's tangents: zero at a local extreme, never steeper than twice the gentler side.
  const tangent: number[] = [slope[0] ?? 0]
  for (let i = 1; i < n - 1; i++) {
    const s0 = slope[i - 1] ?? 0
    const s1 = slope[i] ?? 0
    const h0 = dx[i - 1] ?? 0
    const h1 = dx[i] ?? 0
    const p = (s0 * h1 + s1 * h0) / (h0 + h1 || 1)
    tangent.push(
      (Math.sign(s0) + Math.sign(s1)) * Math.min(Math.abs(s0), Math.abs(s1), 0.5 * Math.abs(p)),
    )
  }
  tangent.push(slope[n - 2] ?? 0)
  let d = `M${String(first[0])},${String(first[1])}`
  for (let i = 0; i < n - 1; i++) {
    const [x0, y0] = points[i] ?? first
    const [x1, y1] = points[i + 1] ?? first
    const h = (dx[i] ?? 0) / 3
    d += `C${String(x0 + h)},${String(y0 + h * (tangent[i] ?? 0))} ${String(x1 - h)},${String(
      y1 - h * (tangent[i + 1] ?? 0),
    )} ${String(x1)},${String(y1)}`
  }
  return d
}

/** Line keys and names of the series, for two or more series. */
export function ChartLegend({ series }: { series: readonly ChartSeries[] }) {
  return (
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
  )
}

/**
 * Scores over time on a fixed 0 to 100 scale. Lines are 2 px monotone curves; a single series
 * also gets a faint wash beneath it. Points have a ring in the surface colour, each series' latest
 * value is labelled at its end, and a crosshair snaps to the date nearest the pointer (or to the
 * point chosen with the arrow keys) with a tooltip. Every value is also in the table view, so
 * the tooltip never gates information.
 */
export function TrendChart({
  series,
  ariaLabel,
  formatX,
  formatY,
  table,
  height = 220,
  legend = true,
}: {
  series: ChartSeries[]
  ariaLabel: string
  formatX: (x: number) => string
  formatY: (y: number) => string
  table: {
    summary: string
    date: string
    series: string
    value: string
    open: string
    note: string
  }
  height?: number
  /** False when the legend is drawn elsewhere, for example beside the chart's filters. */
  legend?: boolean
}) {
  const gradient = useId()
  const box = useRef<HTMLDivElement>(null)
  const [width, setWidth] = useState(640)
  const [active, setActive] = useState<number | null>(null)
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

  // Every point once, in time order: the crosshair and the arrow keys walk this list.
  const points = useMemo(
    () =>
      series
        .flatMap((s) => s.segments.flat().map((point) => ({ point, series: s })))
        .sort((a, b) => a.point.x - b.point.x),
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
  const sy = (y: number) => MARGIN.top + ((100 - y) / 100) * plotH
  const xTicks = ticksBetween(minX, maxX, formatX)
  const current = active === null ? null : (points[active] ?? null)
  const single = series.length === 1
  const noted = points.some(({ point }) => point.note)

  const nearestX = (clientX: number, rect: DOMRect) => {
    const px = clientX - rect.left
    let best: number | null = null
    let distance = Infinity
    points.forEach((candidate, index) => {
      const d = Math.abs(sx(candidate.point.x) - px)
      if (d < distance) {
        best = index
        distance = d
      }
    })
    return best
  }

  // The latest value of each series, labelled at its end unless it would touch another label.
  const ends = series
    .map((s) => ({ series: s, point: s.segments.flat().reduce<ChartPoint | null>(
      (latest, p) => (latest === null || p.x > latest.x ? p : latest),
      null,
    ) }))
    .filter((end): end is { series: ChartSeries; point: ChartPoint } => end.point !== null)
    .sort((a, b) => sy(a.point.y) - sy(b.point.y))
    .filter((end, index, all) => {
      const previous = all[index - 1]
      return !previous || Math.abs(sy(end.point.y) - sy(previous.point.y)) >= 14
    })

  const rows = [...points].reverse()
  return (
    <div className="flex flex-col gap-3">
      {legend && series.length > 1 && <ChartLegend series={series} />}
      <div ref={box} className="relative w-full" style={{ height }}>
        <svg
          role="img"
          aria-label={ariaLabel}
          width={width}
          height={height}
          tabIndex={points.length ? 0 : undefined}
          className={`rounded-md outline-none focus-visible:ring-3 focus-visible:ring-ring/50 ${current?.point.onSelect ? 'cursor-pointer' : ''}`}
          onPointerMove={(event) => {
            setActive(nearestX(event.clientX, event.currentTarget.getBoundingClientRect()))
          }}
          onPointerLeave={() => {
            setActive(null)
          }}
          onBlur={() => {
            setActive(null)
          }}
          onKeyDown={(event) => {
            if (!points.length) return
            if (event.key === 'ArrowRight' || event.key === 'ArrowLeft') {
              event.preventDefault()
              const step = event.key === 'ArrowRight' ? 1 : -1
              setActive((index) =>
                index === null
                  ? step > 0
                    ? 0
                    : points.length - 1
                  : Math.min(points.length - 1, Math.max(0, index + step)),
              )
            } else if (event.key === 'Enter') {
              current?.point.onSelect?.()
            } else if (event.key === 'Escape') {
              setActive(null)
            }
          }}
          onClick={() => {
            current?.point.onSelect?.()
          }}
        >
          <defs>
            {single && series[0] && (
              <linearGradient id={gradient} x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor={series[0].color} stopOpacity={0.16} />
                <stop offset="100%" stopColor={series[0].color} stopOpacity={0} />
              </linearGradient>
            )}
          </defs>
          {Y_TICKS.map((tick) => (
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
                x={MARGIN.left - 8}
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
          {single &&
            series[0]?.segments
              .filter((segment) => segment.length > 1)
              .map((segment) => {
                const coords = segment.map((p) => [sx(p.x), sy(p.y)] as const)
                const first = coords[0]
                const last = coords.at(-1)
                if (!first || !last) return null
                const base = sy(0)
                return (
                  <path
                    key={`wash-${segment[0]?.id ?? ''}`}
                    d={`${monotonePath(coords)}L${String(last[0])},${String(base)}L${String(first[0])},${String(base)}Z`}
                    fill={`url(#${gradient})`}
                  />
                )
              })}
          {current && (
            <line
              x1={sx(current.point.x)}
              x2={sx(current.point.x)}
              y1={MARGIN.top}
              y2={height - MARGIN.bottom}
              stroke="var(--muted-foreground)"
              strokeWidth={1}
              opacity={0.45}
            />
          )}
          {series.map((s) =>
            s.segments
              .filter((segment) => segment.length > 1)
              .map((segment) => (
                <path
                  key={`${s.id}-${segment[0]?.id ?? ''}`}
                  d={monotonePath(segment.map((p) => [sx(p.x), sy(p.y)] as const))}
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
              r={current?.point === point ? 6 : 4}
              fill={point.note ? 'var(--card)' : s.color}
              stroke={point.note ? s.color : 'var(--card)'}
              strokeWidth={2}
              className="transition-[r] duration-150 motion-reduce:transition-none"
            />
          ))}
          {ends.map(({ series: s, point }) => (
            <text
              key={`end-${s.id}`}
              x={sx(point.x) + 9}
              y={sy(point.y)}
              dy="0.32em"
              className="fill-foreground font-heading text-[12px] font-semibold tabular-nums"
            >
              {formatY(point.y)}
            </text>
          ))}
        </svg>
        {current && (
          <div
            aria-hidden="true"
            className="pointer-events-none absolute z-10 min-w-36 -translate-x-1/2 -translate-y-full rounded-lg border bg-popover px-3 py-2 text-xs text-popover-foreground shadow-md"
            style={{
              left: Math.min(Math.max(sx(current.point.x), 72), width - 72),
              top: sy(current.point.y) - 12,
            }}
          >
            <p className="font-heading text-base font-semibold">{formatY(current.point.y)}</p>
            {series.length > 1 && (
              <p className="flex items-center gap-1.5 text-muted-foreground">
                <span
                  className="h-0.5 w-3 rounded-full"
                  style={{ backgroundColor: current.series.color }}
                />
                {current.series.name}
              </p>
            )}
            <p>{current.point.title}</p>
            {current.point.detail && (
              <p className="text-muted-foreground">{current.point.detail}</p>
            )}
            {current.point.note && <p className="max-w-56">{current.point.note}</p>}
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
                {noted && <th className="py-1 pr-3 font-medium">{table.note}</th>}
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
                  {noted && <td className="py-1.5 pr-3">{point.note}</td>}
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
