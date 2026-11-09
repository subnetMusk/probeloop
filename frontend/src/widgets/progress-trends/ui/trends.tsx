import { useQuery } from '@tanstack/react-query'
import { Link, useNavigate } from '@tanstack/react-router'
import { InfoIcon } from 'lucide-react'
import { useState } from 'react'
import type { ReactNode } from 'react'
import { cn } from 'cn'

import { TYPE_COLORS, interviewLabels, isInterviewType, labelOf } from '@/entities/interview'
import { progressQuery } from '@/entities/report'
import { defineMessages, useMessages } from '@/shared/i18n'
import { score, shortDate } from '@/shared/lib/format'
import { useLanguage } from '@/shared/lib/preferences'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/shared/ui/card'
import { FilterPills } from '@/shared/ui/list-card'
import { ChartLegend, TrendChart } from '@/shared/ui/trend-chart'
import { Tooltip, TooltipContent, TooltipTrigger } from '@/shared/ui/tooltip'
import type { ChartPoint, ChartSeries } from '@/shared/ui/trend-chart'
import { trendLines, typesWithScores } from '../model/series'
import type { TrendPoint } from '../model/series'

const messages = defineMessages({
  en: {
    interviews: {
      title: 'Interview scores',
      description: 'The overall score of each interview’s latest report, from 1 to 5.',
      empty: 'The trend starts with the report of your first interview.',
      filter: 'Interview type',
      count: (count: number) => (count === 1 ? '1 report' : `${String(count)} reports`),
      all: 'All',
      chart: (count: number) => `Overall interview scores over time, ${String(count)} reports.`,
    },
    cv: {
      title: 'CV check scores',
      description: 'The overall score of each CV check, from 1 to 5.',
      empty: 'The trend starts with your first CV check.',
      count: (count: number) => (count === 1 ? '1 check' : `${String(count)} checks`),
      chart: (count: number) => `Overall CV check scores over time, ${String(count)} checks.`,
    },
    note: 'Lines join reports scored the same way; a new line starts when the evaluator changes.',
    about: 'How the points are joined',
    scoredBy: (model: string) => `Scored by ${model}`,
    loading: 'Loading…',
    table: {
      summary: 'Show the data as a table',
      date: 'Date',
      series: 'Type',
      value: 'Score',
      open: 'Report',
    },
    open: 'Open report',
  },
  it: {
    interviews: {
      title: 'Punteggi dei colloqui',
      description: 'Il punteggio complessivo dell’ultimo report di ogni colloquio, da 1 a 5.',
      empty: 'L’andamento parte dal report del tuo primo colloquio.',
      filter: 'Tipo di colloquio',
      count: (count: number) => (count === 1 ? '1 report' : `${String(count)} report`),
      all: 'Tutti',
      chart: (count: number) =>
        `Punteggi complessivi dei colloqui nel tempo, ${String(count)} report.`,
    },
    cv: {
      title: 'Punteggi dei CV check',
      description: 'Il punteggio complessivo di ogni controllo del CV, da 1 a 5.',
      empty: 'L’andamento parte dal tuo primo CV check.',
      count: (count: number) => (count === 1 ? '1 controllo' : `${String(count)} controlli`),
      chart: (count: number) => `Punteggi complessivi dei CV check nel tempo, ${String(count)}.`,
    },
    note: 'Le linee uniscono report valutati allo stesso modo; una nuova linea parte quando cambia il valutatore.',
    about: 'Come vengono uniti i punti',
    scoredBy: (model: string) => `Valutato da ${model}`,
    loading: 'Caricamento…',
    table: {
      summary: 'Mostra i dati in tabella',
      date: 'Data',
      series: 'Tipo',
      value: 'Punteggio',
      open: 'Report',
    },
    open: 'Apri il report',
  },
})

const readableModel = (ref: string) => ref.replace(/^chatgpt:/, '').replace(/^ollama:/, '')

/** Chart points that open their report, by click or from the table view. */
function useChartPoints() {
  const t = useMessages(messages)
  const language = useLanguage()
  const navigate = useNavigate()
  const base = (p: TrendPoint) => ({
    id: p.reportId,
    x: p.createdAt,
    y: p.overall,
    title: shortDate(p.createdAt, language),
    detail: t.scoredBy(readableModel(p.modelRef)),
  })
  const linkClass = 'text-brand-text underline'
  return {
    interview: (p: TrendPoint): ChartPoint => {
      const params = { sessionId: p.sessionId ?? p.subjectId, reportId: p.reportId }
      const to = '/interviews/$sessionId/reports/$reportId'
      return {
        ...base(p),
        onSelect: () => void navigate({ to, params }),
        link: (
          <Link to={to} params={params} className={linkClass}>
            {t.open}
          </Link>
        ),
      }
    },
    cv: (p: TrendPoint): ChartPoint => {
      const params = { snapshotId: p.subjectId, reportId: p.reportId }
      const to = '/cv-checks/$snapshotId/reports/$reportId'
      return {
        ...base(p),
        onSelect: () => void navigate({ to, params }),
        link: (
          <Link to={to} params={params} className={linkClass}>
            {t.open}
          </Link>
        ),
      }
    },
  }
}

const CHART_HEIGHT = 220

/**
 * One trend card. Both cards share this structure (title, a row for filters or a caption and
 * the legend, then a chart of fixed height), so they line up side by side.
 */
function TrendCard({
  title,
  description,
  info,
  controls,
  series,
  label,
  empty,
  pending,
}: {
  title: string
  description: string
  info?: ReactNode
  controls: ReactNode
  series: ChartSeries[]
  label: string
  empty: string
  pending: boolean
}) {
  const t = useMessages(messages)
  const language = useLanguage()
  const placeholder = (text: string, dashed: boolean) => (
    <p
      className={cn(
        'flex items-center justify-center rounded-lg px-4 text-center text-sm text-muted-foreground',
        dashed && 'border border-dashed',
      )}
      style={{ height: CHART_HEIGHT }}
    >
      {text}
    </p>
  )
  const chart = pending ? (
    placeholder(t.loading, false)
  ) : series.every((s) => s.segments.length === 0) ? (
    placeholder(empty, true)
  ) : (
    <TrendChart
      series={series}
      ariaLabel={label}
      formatX={(x) => shortDate(x, language)}
      formatY={(y) => score(y, language)}
      table={t.table}
      height={CHART_HEIGHT}
      legend={false}
    />
  )
  return (
    <Card className="h-full">
      <CardHeader>
        <div className="flex items-center gap-1.5">
          <CardTitle role="heading" aria-level={2}>
            {title}
          </CardTitle>
          {info}
        </div>
        <CardDescription>{description}</CardDescription>
      </CardHeader>
      <CardContent className="flex flex-1 flex-col gap-3">
        <div className="flex min-h-8 flex-wrap items-center justify-between gap-x-4 gap-y-2">
          {controls}
          {series.length > 1 && <ChartLegend series={series} />}
        </div>
        {chart}
      </CardContent>
    </Card>
  )
}

/** Interview scores over time, all types or one at a time. */
export function InterviewTrend() {
  const t = useMessages(messages)
  const labels = useMessages(interviewLabels)
  const progress = useQuery(progressQuery)
  const points = useChartPoints()
  const [chosen, setChosen] = useState('all')
  const groups = progress.data ?? []
  const types = typesWithScores(groups)
  const type = types.includes(chosen) ? chosen : 'all'
  const series: ChartSeries[] = trendLines(
    groups,
    'interview',
    type === 'all' ? undefined : type,
  ).map((line) => ({
    id: line.key,
    name: labelOf(labels, 'types', line.key),
    color: isInterviewType(line.key) ? TYPE_COLORS[line.key] : 'var(--chart-5)',
    segments: line.segments.map((run) => run.map(points.interview)),
  }))
  const count = series.reduce((sum, s) => sum + s.segments.flat().length, 0)
  return (
    <TrendCard
      title={t.interviews.title}
      description={t.interviews.description}
      info={
        <Tooltip>
          <TooltipTrigger asChild>
            <button
              type="button"
              aria-label={t.about}
              className="rounded-full text-muted-foreground outline-none hover:text-foreground focus-visible:ring-3 focus-visible:ring-ring/50"
            >
              <InfoIcon className="size-4" aria-hidden="true" />
            </button>
          </TooltipTrigger>
          <TooltipContent className="max-w-xs">{t.note}</TooltipContent>
        </Tooltip>
      }
      controls={
        types.length > 1 ? (
          <FilterPills
            label={t.interviews.filter}
            value={type}
            onChange={setChosen}
            options={['all', ...types].map((value) => ({
              value,
              label: value === 'all' ? t.interviews.all : labelOf(labels, 'types', value),
            }))}
          />
        ) : (
          <span className="text-xs text-muted-foreground">{t.interviews.count(count)}</span>
        )
      }
      series={series}
      label={t.interviews.chart(count)}
      empty={t.interviews.empty}
      pending={progress.isPending}
    />
  )
}

/** CV check scores over time. */
export function CvTrend() {
  const t = useMessages(messages)
  const progress = useQuery(progressQuery)
  const points = useChartPoints()
  const series: ChartSeries[] = trendLines(progress.data ?? [], 'cv').map((line) => ({
    id: line.key,
    name: t.cv.title,
    color: 'var(--chart-2)',
    segments: line.segments.map((run) => run.map(points.cv)),
  }))
  const count = series.reduce((sum, s) => sum + s.segments.flat().length, 0)
  return (
    <TrendCard
      title={t.cv.title}
      description={t.cv.description}
      controls={<span className="text-xs text-muted-foreground">{t.cv.count(count)}</span>}
      series={series}
      label={t.cv.chart(count)}
      empty={t.cv.empty}
      pending={progress.isPending}
    />
  )
}
