import type { ReportData } from '@/api/rest'
import { Badge } from '@/components/ui/badge'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { sessionFile } from '@/api/rest'

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
  summary: 'Sintesi',
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
            <>
              <a
                className="ml-2 text-indigo-600 underline"
                href={`/sessions/${report.session_id}#turn-${item.turn_seq}`}
              >
                {it ? 'Turno' : 'Turn'} {item.turn_seq}
              </a>
              <audio
                className="mt-2 h-8 w-full max-w-sm"
                controls
                preload="none"
                aria-label={`${it ? 'Audio del turno' : 'Turn audio'} ${item.turn_seq}`}
                src={sessionFile(
                  report.session_id,
                  `audio/turn-${String(item.turn_seq).padStart(4, '0')}-candidate.wav`,
                )}
              />
            </>
          )}
        </blockquote>
      ))}
    </div>
  )
  return (
    <div className="flex flex-col gap-6" data-testid="report-content">
      <div className="flex flex-wrap gap-2">
        {(['md', 'json', 'pdf'] as const).map((format) => (
          <Button key={format} asChild variant="outline" size="sm">
            <a href={`/api/reports/${report.id}/export/${format}`} download>
              {format.toUpperCase()}
            </a>
          </Button>
        ))}
        {report.session_id && (
          <Button asChild variant="outline" size="sm">
            <a href={sessionFile(report.session_id, 'audio/interview.wav')} download>
              {it ? 'Registrazione' : 'Recording'}
            </a>
          </Button>
        )}
      </div>
      <div className="rounded-lg border p-5">
        <p className="text-sm text-muted-foreground">{report.disclaimer}</p>
        <p className="mt-4 text-3xl font-semibold">
          {report.overall === null
            ? it
              ? 'Evidenza insufficiente per il voto complessivo'
              : 'Insufficient evidence for an overall score'
            : `${report.overall.toFixed(1)} / 5`}
        </p>
        {report.overall !== null && (
          <p className="font-medium">
            {report.overall >= 4
              ? it
                ? 'Solido'
                : 'Solid'
              : report.overall >= 2.5
                ? it
                  ? 'In sviluppo'
                  : 'Developing'
                : it
                  ? 'Da migliorare'
                  : 'Needs work'}
          </p>
        )}
        <p className="mt-2 text-sm">
          {report.assessed}/{report.criteria} {it ? 'criteri valutabili' : 'assessable criteria'} ·{' '}
          {report.rubric_id} · v{report.version}
        </p>
        <p className="text-xs text-muted-foreground">
          {it ? 'Tempo di elaborazione' : 'Processing time'}: {Math.round(report.duration_s)} s ·{' '}
          {report.model_ref}
        </p>
      </div>
      {report.units.length > 0 && (
        <section
          className="flex flex-col gap-4"
          aria-label={it ? 'Valutazioni delle risposte' : 'Answer assessments'}
        >
          <h2 className="text-xl font-semibold">
            {it ? 'Risposte e approfondimenti' : 'Answers and follow-ups'}
          </h2>
          {report.units.map((unit) => (
            <details key={unit.id} className="rounded-lg border p-4">
              <summary className="cursor-pointer font-medium">
                {unit.id} · {unit.kind} · {it ? 'risposte' : 'answers'}{' '}
                {unit.answer_seqs.join(', ')}
              </summary>
              <p className="my-2 text-sm text-muted-foreground">
                {it ? 'Domande' : 'Questions'}: {unit.question_seqs.join(', ')}
              </p>
              {unit.kind === 'logistics' && (
                <p>
                  {it
                    ? 'Logistica e chiusura: senza voto.'
                    : 'Logistics and closing are not scored.'}
                </p>
              )}
              {unit.kind === 'unclassified' && (
                <p>
                  {it
                    ? 'Tipo di domanda non identificato con affidabilità: senza voto.'
                    : 'Question kind could not be classified reliably: not scored.'}
                </p>
              )}
              {report.unit_scores
                .filter((score) => score.unit_id === unit.id)
                .map((score) => (
                  <article key={score.criterion_id} className="flex flex-col gap-2 border-t py-3">
                    <h3 className="font-medium">
                      {score.label}: {score.value?.toFixed(1) ?? 'NA'} / 5{' '}
                      {score.unstable && (
                        <Badge variant="destructive">{it ? 'Instabile' : 'Unstable'}</Badge>
                      )}
                    </h3>
                    <p className="whitespace-pre-line text-sm">{score.reason}</p>
                    {evidence(score.evidence)}
                  </article>
                ))}
            </details>
          ))}
        </section>
      )}
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
      {report.delivery.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle>{it ? 'Misure di esposizione' : 'Delivery measures'}</CardTitle>
          </CardHeader>
          <CardContent className="flex flex-col gap-3">
            {report.delivery.map((metric, index) => (
              <div key={index} className="border-b pb-2">
                <p className="text-sm font-medium">
                  {metric.id.replaceAll('_', ' ')}{' '}
                  {metric.turn_seq !== null && `· ${it ? 'turno' : 'turn'} ${metric.turn_seq}`}:{' '}
                  {metric.value ?? 'NA'} {metric.unit}
                </p>
                <p className="text-xs text-muted-foreground">{metric.detail}</p>
              </div>
            ))}
          </CardContent>
        </Card>
      )}
      <details className="rounded-lg border p-4 text-xs text-muted-foreground">
        <summary className="cursor-pointer">
          {it ? 'Versioni e provenienza' : 'Versions and provenance'}
        </summary>
        <p className="mt-2 break-all">{report.input_fingerprint}</p>
        <p className="break-all">{report.rubric_hash}</p>
        <p>{report.prompt_ref}</p>
        <p>{report.revisions.map((r) => `${r.seq}:v${r.revision}`).join(', ')}</p>
      </details>
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
