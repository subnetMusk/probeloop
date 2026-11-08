import type { ReportData } from '@/api/rest'
import { Badge } from '@/components/ui/badge'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'

const LABELS: Record<string, string> = {
  relevance: 'Pertinenza rispetto al ruolo',
  impact: 'Evidenza dei risultati',
  ownership: 'Specificità e contributo personale',
  clarity: 'Chiarezza e struttura',
  consistency: 'Coerenza interna',
  depth: 'Profondità rispetto al livello',
  readability: 'Leggibilità automatica',
}
const KINDS: Record<string, string> = {
  strength: 'Punto di forza',
  improvement: 'Da migliorare',
  rewrite: 'Proposta di riscrittura',
  question: 'Domanda per esercitarti',
  technical_error: 'Verifica tecnica del modello',
}

export function ReportContent({ report }: { report: ReportData }) {
  const it = report.language === 'it'
  const evidence = (items: ReportData['scores'][number]['evidence']) => (
    <div className="flex flex-col gap-2">
      {items.map((item, index) => (
        <blockquote
          key={`${item.source_id}-${index}`}
          className="border-l-2 pl-3 text-sm text-muted-foreground"
        >
          “{item.quote}”
          {item.turn_seq !== null && item.turn_seq !== undefined && report.session_id && (
            <a
              className="ml-2 text-indigo-600 underline"
              href={`/sessions/${report.session_id}#turn-${item.turn_seq}`}
            >
              {it ? 'Turno' : 'Turn'} {item.turn_seq}
            </a>
          )}
        </blockquote>
      ))}
    </div>
  )
  return (
    <div className="flex flex-col gap-6" data-testid="report-content">
      <div className="rounded-lg border p-5">
        <p className="text-sm text-muted-foreground">{report.disclaimer}</p>
        <p className="mt-4 text-3xl font-semibold">
          {report.overall === null
            ? it
              ? 'Evidenza insufficiente per il voto complessivo'
              : 'Insufficient evidence for an overall score'
            : `${report.overall.toFixed(1)} / 5`}
        </p>
        <p className="mt-2 text-sm">
          {report.assessed}/{report.criteria} {it ? 'criteri valutabili' : 'assessable criteria'} ·{' '}
          {report.rubric_id} · v{report.version}
        </p>
        <p className="text-xs text-muted-foreground">
          {it ? 'Tempo di elaborazione' : 'Processing time'}: {Math.round(report.duration_s)} s ·{' '}
          {report.model_ref}
        </p>
      </div>
      <div className="grid gap-4 md:grid-cols-2">
        {report.scores.map((score, index) => (
          <Card key={`${score.criterion_id}-${index}`}>
            <CardHeader>
              <CardTitle>
                {it ? (LABELS[score.criterion_id] ?? score.label) : score.label}
              </CardTitle>
            </CardHeader>
            <CardContent className="flex flex-col gap-3">
              <Badge variant={score.value === null ? 'secondary' : 'outline'}>
                {score.value === null
                  ? it
                    ? 'Non valutabile'
                    : 'Not assessable'
                  : `${score.value.toFixed(1)} / 5`}
              </Badge>
              {score.unstable && (
                <Badge variant="destructive">
                  {it ? 'Valutazione instabile' : 'Unstable judgement'}
                </Badge>
              )}
              <p className="whitespace-pre-line text-sm">{score.reason}</p>
              {evidence(score.evidence)}
            </CardContent>
          </Card>
        ))}
      </div>
      <Card>
        <CardHeader>
          <CardTitle>
            {it
              ? 'Osservazioni del modello con citazioni verificate'
              : 'Model observations with verified quotations'}
          </CardTitle>
        </CardHeader>
        <CardContent className="flex flex-col gap-5">
          {report.observations.length === 0 && (
            <p>
              {it
                ? 'Nessuna osservazione supportata da evidenze.'
                : 'No evidence-backed observations.'}
            </p>
          )}
          {report.observations.map((observation, index) => (
            <article key={index} className="flex flex-col gap-2 border-b pb-4 last:border-0">
              <Badge variant="outline" className="self-start">
                {it
                  ? (KINDS[observation.kind] ?? observation.kind)
                  : observation.kind.replaceAll('_', ' ')}
              </Badge>
              <p>{observation.text}</p>
              {evidence(observation.evidence)}
              {observation.replacement && (
                <p className="rounded-md bg-muted p-3 text-sm">{observation.replacement}</p>
              )}
            </article>
          ))}
        </CardContent>
      </Card>
      <Card>
        <CardHeader>
          <CardTitle>
            {it ? 'Controlli misurabili e limiti' : 'Measured checks and limitations'}
          </CardTitle>
        </CardHeader>
        <CardContent>
          <ul className="flex flex-col gap-3">
            {report.checks.map((check, index) => (
              <li key={`${check.id}-${index}`} className="flex flex-col gap-1">
                <div className="flex flex-wrap gap-2">
                  <Badge variant="outline">{check.status.replaceAll('_', ' ')}</Badge>
                  <span className="text-sm">{check.detail}</span>
                </div>
                {evidence(check.evidence)}
              </li>
            ))}
          </ul>
        </CardContent>
      </Card>
      {report.dropped > 0 && (
        <p className="text-sm text-muted-foreground">
          {it
            ? 'Elementi del modello scartati durante la validazione'
            : 'Model items discarded during validation'}
          : {report.dropped}
        </p>
      )}
    </div>
  )
}
