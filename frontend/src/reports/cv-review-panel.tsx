import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Link } from '@tanstack/react-router'
import { useEffect } from 'react'

import { api, isRunning } from '@/api/rest'
import type { JobView } from '@/api/rest'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Progress } from '@/components/ui/progress'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { setLanguage, useLanguage } from '@/settings/preferences'
import { rememberReportJob } from '@/reports/pending-jobs'

export function CvReviewPanel({
  snapshotId,
  onBusyChange,
}: {
  snapshotId: string
  onBusyChange?: (busy: boolean) => void
}) {
  const language = useLanguage()
  const it = language === 'it'
  const queryClient = useQueryClient()
  const reportsKey = ['cv-reviews', snapshotId]
  const jobsKey = ['cv-jobs', snapshotId]
  const jobs = useQuery({
    queryKey: jobsKey,
    queryFn: async () => {
      const list = await api.snapshotJobs(snapshotId)
      const previous = queryClient.getQueryData<JobView[]>(jobsKey)
      if (previous?.some(isRunning) && !list.some(isRunning))
        void queryClient.invalidateQueries({ queryKey: reportsKey })
      return list
    },
    refetchInterval: (query) => (query.state.data?.some(isRunning) ? 1500 : false),
  })
  const reports = useQuery({ queryKey: reportsKey, queryFn: () => api.cvReviews(snapshotId) })
  const latestJob = jobs.data?.filter((j) => j.kind === 'review_cv').at(-1)
  const running = isRunning(latestJob)
  const start = useMutation({
    mutationFn: () => api.reviewCv(snapshotId, language),
    onSuccess: (job) => {
      rememberReportJob(job.id)
      queryClient.setQueryData<JobView[]>(jobsKey, (old) => [...(old ?? []), job])
      void queryClient.invalidateQueries({ queryKey: jobsKey })
    },
  })
  useEffect(() => {
    onBusyChange?.(running || start.isPending)
  }, [running, start.isPending, onBusyChange])
  return (
    <Card data-testid="cv-review-panel">
      <CardHeader>
        <CardTitle>{it ? 'Revisione del CV' : 'CV review'}</CardTitle>
        <CardDescription>
          {it
            ? 'Valuta il documento prima del colloquio, anche senza attivare il microfono. Ogni rigenerazione conserva la versione precedente.'
            : 'Review the document before an interview, without enabling the microphone. Regeneration keeps earlier versions.'}
        </CardDescription>
      </CardHeader>
      <CardContent className="flex flex-col gap-4">
        <Select
          value={language}
          onValueChange={(value) => {
            setLanguage(value === 'en' ? 'en' : 'it')
          }}
        >
          <SelectTrigger aria-label={it ? 'Lingua del report' : 'Report language'}>
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="it">Italiano</SelectItem>
            <SelectItem value="en">English</SelectItem>
          </SelectContent>
        </Select>
        {running && latestJob && (
          <div aria-live="polite">
            <p>
              {it ? 'Revisione in elaborazione' : 'Review in progress'}:{' '}
              {latestJob.message ?? latestJob.status}
            </p>
            <Progress value={latestJob.progress * 100} />
          </div>
        )}
        {latestJob?.status === 'failed' && (
          <p role="alert" className="text-destructive">
            {latestJob.error}
          </p>
        )}
        <Button
          className="self-start"
          disabled={running || start.isPending}
          onClick={() => {
            start.mutate()
          }}
        >
          {it ? 'Genera revisione CV' : 'Generate CV review'}
        </Button>
        {start.error && (
          <p role="alert" className="text-destructive">
            {start.error.message}
          </p>
        )}
        {reports.error && (
          <p role="alert" className="text-destructive">
            {reports.error.message}
          </p>
        )}
        <ul className="flex flex-col gap-2">
          {reports.data?.toReversed().map((report) => (
            <li key={report.id}>
              <Link
                className="text-indigo-600 underline"
                to="/reports/$reportId"
                params={{ reportId: report.id }}
              >
                {it ? 'Apri revisione' : 'Open review'} v{report.version} ·{' '}
                {report.language.toUpperCase()} · {report.assessed}/{report.criteria}{' '}
                {it ? 'criteri valutabili' : 'assessable criteria'}
              </Link>
            </li>
          ))}
        </ul>
      </CardContent>
    </Card>
  )
}
