import { useQuery } from '@tanstack/react-query'
import { Link } from '@tanstack/react-router'
import { useState } from 'react'

import { api } from '@/api/rest'
import type { ProgressGroup } from '@/api/rest'
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card'
import { Label } from '@/components/ui/label'
import {
  Select,
  SelectTrigger,
  SelectContent,
  SelectItem,
  SelectValue,
} from '@/components/ui/select'
import { dateTime } from '@/lib/format'
import { useLanguage } from '@/settings/preferences'

function Trend({ group }: { group: ProgressGroup }) {
  const it = useLanguage() === 'it'
  const [criterion, setCriterion] = useState('overall')
  const value = (point: ProgressGroup['points'][number]) =>
    criterion === 'overall' ? point.overall : (point.values[criterion] ?? null)
  const points = group.points.map((point, index) => ({
    point,
    value: value(point),
    x: 35 + (index * 390) / Math.max(1, group.points.length - 1),
  }))
  const y = (score: number) => 160 - (score - 1) * 32
  return (
    <div className="flex flex-col gap-3 rounded-lg border p-4">
      <p className="text-sm">
        {group.rubric_id} · {group.language.toUpperCase()} · {group.points.length}{' '}
        {it ? 'colloqui confrontabili' : 'comparable interviews'}
      </p>
      <Label htmlFor={`criterion-${group.id}`}>
        {it ? 'Criterio da confrontare' : 'Criterion to compare'}
      </Label>
      <Select value={criterion} onValueChange={setCriterion}>
        <SelectTrigger id={`criterion-${group.id}`}>
          <SelectValue />
        </SelectTrigger>
        <SelectContent>
          <SelectItem value="overall">{it ? 'Complessivo' : 'Overall'}</SelectItem>
          {Object.entries(group.criteria).map(([id, label]) => (
            <SelectItem key={id} value={id}>
              {label}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
      {points.length < 2 ? (
        <p className="text-sm text-muted-foreground">
          {it
            ? 'Servono almeno due colloqui confrontabili per mostrare una tendenza.'
            : 'At least two comparable interviews are needed for a trend.'}
        </p>
      ) : (
        <svg
          viewBox="0 0 450 190"
          className="w-full text-indigo-600 dark:text-indigo-400"
          role="img"
          aria-label={
            it
              ? 'Andamento del voto da 1 a 5, in ordine di report'
              : 'Scores from 1 to 5 in report order'
          }
        >
          {[1, 3, 5].map((score) => (
            <g key={score}>
              <line
                x1="30"
                x2="430"
                y1={y(score)}
                y2={y(score)}
                stroke="currentColor"
                opacity="0.15"
              />
              <text x="10" y={y(score) + 4} fill="currentColor" fontSize="11">
                {score}
              </text>
            </g>
          ))}
          {points.map((item, index) => {
            const previous = points[index - 1]
            return (
              <g key={item.point.report_id}>
                {item.value !== null &&
                  previous?.value !== null &&
                  previous?.value !== undefined && (
                    <line
                      x1={previous.x}
                      y1={y(previous.value)}
                      x2={item.x}
                      y2={y(item.value)}
                      stroke="currentColor"
                      strokeWidth="2"
                    />
                  )}
                {item.value !== null ? (
                  <a
                    href={`/reports/${item.point.report_id}`}
                    aria-label={`${dateTime(item.point.created_at)}: ${item.value} / 5`}
                  >
                    <circle cx={item.x} cy={y(item.value)} r="5" fill="currentColor" />
                    <title>
                      {dateTime(item.point.created_at)}: {item.value} / 5
                    </title>
                  </a>
                ) : (
                  <text x={item.x} y="90" textAnchor="middle" fontSize="10" fill="currentColor">
                    NA
                  </text>
                )}
                <text x={item.x} y="183" textAnchor="middle" fontSize="10" fill="currentColor">
                  {index + 1}
                </text>
              </g>
            )
          })}
        </svg>
      )}
      <ul className="flex flex-col gap-1 text-sm">
        {points.map(({ point, value }, index) => (
          <li key={point.report_id}>
            <Link
              className="underline"
              to="/reports/$reportId"
              params={{ reportId: point.report_id }}
            >
              {index + 1}. {dateTime(point.created_at)}
            </Link>{' '}
            · {value ?? 'NA'} / 5
            {criterion !== 'overall' &&
              ` · ${point.evidence_counts[criterion] ?? 0} ${it ? 'risposte valutabili' : 'assessable answers'}`}
          </li>
        ))}
      </ul>
    </div>
  )
}

export function ProgressHistory() {
  const it = useLanguage() === 'it'
  const groups = useQuery({ queryKey: ['progress'], queryFn: api.progress })
  const reports = useQuery({ queryKey: ['report-history'], queryFn: api.reportHistory })
  return (
    <Card>
      <CardHeader>
        <CardTitle>{it ? 'Report e progressi' : 'Reports and progress'}</CardTitle>
      </CardHeader>
      <CardContent className="flex flex-col gap-5">
        <p className="text-sm text-muted-foreground">
          {it
            ? 'Una sola versione, la più recente, per ogni colloquio. Si confrontano solo rubriche, criteri, modello, istruzioni di valutazione e lingua uguali. I voti non valutabili restano vuoti.'
            : 'Only the latest version of each interview contributes a point. Rubric, criteria, model, assessment instructions and language must match. Unassessable values remain missing.'}
        </p>
        {(groups.data?.length ?? 0) > 1 && (
          <p role="status">
            {it
              ? 'Questi gruppi non sono confrontabili tra loro; le tendenze restano separate.'
              : 'These groups cannot be compared with each other; trends remain separate.'}
          </p>
        )}
        {groups.data?.map((group) => (
          <Trend key={group.id} group={group} />
        ))}
        <h2 className="font-semibold">
          {it ? 'Revisioni CV e report recenti' : 'Latest CV reviews and interview reports'}
        </h2>
        <ul className="flex flex-col gap-2">
          {reports.data?.map((report) => (
            <li key={report.id}>
              <Link className="underline" to="/reports/$reportId" params={{ reportId: report.id }}>
                {report.kind === 'cv'
                  ? it
                    ? 'Revisione CV'
                    : 'CV review'
                  : it
                    ? 'Colloquio'
                    : 'Interview'}{' '}
                · {dateTime(report.created_at)} · v{report.version} · {report.overall ?? 'NA'} / 5
              </Link>
            </li>
          ))}
        </ul>
        {reports.data?.length === 0 && (
          <p>
            {it
              ? 'Genera un report per iniziare a seguire i progressi.'
              : 'Generate a report to start tracking progress.'}
          </p>
        )}
        {(groups.error ?? reports.error) && (
          <p role="alert" className="text-destructive">
            {(groups.error ?? reports.error)?.message}
          </p>
        )}
      </CardContent>
    </Card>
  )
}
