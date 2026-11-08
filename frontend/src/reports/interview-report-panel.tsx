import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Link } from '@tanstack/react-router'

import { api, isRunning } from '@/api/rest'
import type { JobView } from '@/api/rest'
import { Button } from '@/components/ui/button'
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from '@/components/ui/card'
import { Progress } from '@/components/ui/progress'
import { rememberReportJob } from '@/reports/pending-jobs'
import { useLanguage } from '@/settings/preferences'
import { T } from '@/settings/translated-text'

export function InterviewReportPanel({ sessionId, jobs }: { sessionId: string; jobs: JobView[] }) {
  const language = useLanguage()
  const it = language === 'it'
  const client = useQueryClient()
  const latest = jobs.filter((j) => j.kind === 'review_interview').at(-1)
  const running = isRunning(latest)
  const refinement = jobs.some((j) => j.kind === 'refine_transcript' && isRunning(j))
  const reports = useQuery({
    queryKey: ['interview-reports', sessionId],
    queryFn: () => api.interviewReports(sessionId),
    refetchInterval: running ? 1500 : false,
  })
  const start = useMutation({
    mutationFn: () => api.reviewInterview(sessionId, language),
    onSuccess: (job) => {
      rememberReportJob(job.id)
      client.setQueryData<JobView[]>(['jobs', sessionId], (old) => [...(old ?? []), job])
      void client.invalidateQueries({ queryKey: ['jobs', sessionId] })
    },
  })
  return (
    <Card data-testid="interview-report-panel">
      <CardHeader>
        <CardTitle>{it ? 'Valutazione del colloquio' : 'Interview assessment'}</CardTitle>
        <CardDescription>
          {it
            ? 'Controlla il trascritto, poi genera il report. Viene conservata la revisione scelta ora. Puoi lasciare questa pagina: riceverai un avviso al termine.'
            : 'Review the transcript, then generate a report. The current revisions are frozen. You can leave this page and receive a completion notice.'}
        </CardDescription>
      </CardHeader>
      <CardContent className="flex flex-col gap-3">
        <p className="text-sm text-muted-foreground">
          {it
            ? 'Ogni risposta viene giudicata due volte, con le ancore in ordine opposto, poi viene scritta una sintesi: di solito pochi minuti. Il tempo effettivo compare nel report.'
            : 'Each answer is judged twice, with the anchors in opposite order, then a summary is written: usually a few minutes. Actual duration appears in the report.'}
        </p>
        <Button
          className="self-start"
          disabled={running || refinement || start.isPending}
          onClick={() => {
            start.mutate()
          }}
        >
          {it ? 'Genera report' : 'Generate report'}
        </Button>
        {refinement && (
          <p role="status">
            {it ? 'Attendi la rifinitura del trascritto.' : 'Waiting for transcript refinement.'}
          </p>
        )}
        {running && latest && (
          <div role="status">
            <p>{latest.message ?? latest.status}</p>
            <Progress value={latest.progress * 100} />
          </div>
        )}
        {latest?.status === 'failed' && (
          <p role="alert" className="text-destructive">
            {latest.error && <T text={latest.error} />}
          </p>
        )}
        {(start.error ?? reports.error) && (
          <p role="alert" className="text-destructive">
            {(start.error ?? reports.error)?.message}
          </p>
        )}
        <ul>
          {reports.data?.toReversed().map((report) => (
            <li key={report.id}>
              <Link className="underline" to="/reports/$reportId" params={{ reportId: report.id }}>
                {it ? 'Apri report' : 'Open report'} v{report.version} ·{' '}
                {report.language.toUpperCase()} · {report.overall ?? 'NA'} / 5
              </Link>
            </li>
          ))}
        </ul>
      </CardContent>
    </Card>
  )
}
