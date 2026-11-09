import { useQuery } from '@tanstack/react-query'
import { Link, useNavigate } from '@tanstack/react-router'
import { useState } from 'react'

import { TYPE_COLORS, interviewLabels, isInterviewType, labelOf } from '@/entities/interview'
import { progressQuery } from '@/entities/report'
import { defineMessages, useMessages } from '@/shared/i18n'
import { score, shortDate } from '@/shared/lib/format'
import { useLanguage } from '@/shared/lib/preferences'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/shared/ui/card'
import { FilterPills } from '@/shared/ui/list-card'
import { TrendChart } from '@/shared/ui/trend-chart'
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
      all: 'All',
      chart: (count: number) => `Overall interview scores over time, ${String(count)} reports.`,
    },
    cv: {
      title: 'CV check scores',
      description: 'The overall score of each CV check, from 1 to 5.',
      empty: 'The trend starts with your first CV check.',
      chart: (count: number) => `Overall CV check scores over time, ${String(count)} checks.`,
    },
    note: 'Lines join reports scored the same way; a new line starts when the evaluator changes.',
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
      all: 'Tutti',
      chart: (count: number) =>
        `Punteggi complessivi dei colloqui nel tempo, ${String(count)} report.`,
    },
    cv: {
      title: 'Punteggi dei CV check',
      description: 'Il punteggio complessivo di ogni controllo del CV, da 1 a 5.',
      empty: 'L’andamento parte dal tuo primo CV check.',
      chart: (count: number) => `Punteggi complessivi dei CV check nel tempo, ${String(count)}.`,
    },
    note: 'Le linee uniscono report valutati allo stesso modo; una nuova linea parte quando cambia il valutatore.',
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

function Chart({
  series,
  label,
  empty,
  pending,
}: {
  series: ChartSeries[]
  label: string
  empty: string
  pending: boolean
}) {
  const t = useMessages(messages)
  const language = useLanguage()
  if (pending) return <p className="py-16 text-center text-sm text-muted-foreground">{t.loading}</p>
  if (series.every((s) => s.segments.length === 0))
    return (
      <p className="rounded-lg border border-dashed px-4 py-16 text-center text-sm text-muted-foreground">
        {empty}
      </p>
    )
  return (
    <TrendChart
      series={series}
      ariaLabel={label}
      formatX={(x) => shortDate(x, language)}
      formatY={(y) => score(y, language)}
      table={t.table}
    />
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
    <Card>
      <CardHeader className="flex flex-wrap items-start justify-between gap-3">
        <div className="flex flex-col gap-1">
          <CardTitle role="heading" aria-level={2}>
            {t.interviews.title}
          </CardTitle>
          <CardDescription>{t.interviews.description}</CardDescription>
        </div>
        {types.length > 1 && (
          <FilterPills
            label={t.interviews.filter}
            value={type}
            onChange={setChosen}
            options={['all', ...types].map((value) => ({
              value,
              label: value === 'all' ? t.interviews.all : labelOf(labels, 'types', value),
            }))}
          />
        )}
      </CardHeader>
      <CardContent className="flex flex-col gap-2">
        <Chart
          series={series}
          label={t.interviews.chart(count)}
          empty={t.interviews.empty}
          pending={progress.isPending}
        />
        {count > 1 && <p className="text-xs text-muted-foreground">{t.note}</p>}
      </CardContent>
    </Card>
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
    <Card>
      <CardHeader>
        <CardTitle role="heading" aria-level={2}>
          {t.cv.title}
        </CardTitle>
        <CardDescription>{t.cv.description}</CardDescription>
      </CardHeader>
      <CardContent>
        <Chart
          series={series}
          label={t.cv.chart(count)}
          empty={t.cv.empty}
          pending={progress.isPending}
        />
      </CardContent>
    </Card>
  )
}
