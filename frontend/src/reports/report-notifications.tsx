import { useQuery, useQueryClient } from '@tanstack/react-query'
import { Link } from '@tanstack/react-router'

import { api, isRunning } from '@/api/rest'
import { Button } from '@/components/ui/button'
import { dismissReportJob, useReportJobs } from '@/reports/pending-jobs'
import { useLanguage } from '@/settings/preferences'
import { T } from '@/settings/translated-text'

export function ReportNotifications() {
  const ids = useReportJobs()
  const it = useLanguage() === 'it'
  const client = useQueryClient()
  const jobs = useQuery({
    queryKey: ['report-notifications', ids],
    queryFn: async () => {
      const jobs = await Promise.all(
        ids.map(async (id) => {
          try {
            return { id, job: await api.job(id) }
          } catch {
            return { id, job: null }
          }
        }),
      )
      if (jobs.some(({ job }) => job?.status === 'succeeded')) {
        void client.invalidateQueries({ queryKey: ['interview-reports'] })
        void client.invalidateQueries({ queryKey: ['cv-reviews'] })
      }
      return jobs
    },
    enabled: ids.length > 0,
    refetchInterval: (query) =>
      query.state.data?.some(({ job }) => job === null || isRunning(job)) ? 3000 : false,
  })
  return (
    <div className="mx-auto max-w-5xl px-6" aria-live="polite">
      {jobs.data
        ?.filter(({ job }) => !isRunning(job ?? undefined))
        .map(({ id, job }) => {
          const reportId = job?.result?.report_id
          return (
            <div
              key={id}
              className="my-2 flex items-center gap-3 rounded-lg border p-3 text-sm"
              role="status"
            >
              {job?.status === 'succeeded' && typeof reportId === 'string' ? (
                <Link className="underline" to="/reports/$reportId" params={{ reportId }}>
                  {it ? 'Il report è pronto' : 'Your report is ready'}
                </Link>
              ) : (
                <span>
                  {it
                    ? 'Elaborazione non riuscita o non disponibile'
                    : 'Processing failed or unavailable'}
                  : {job?.error && <T text={job.error} />}
                </span>
              )}
              <Button
                variant="ghost"
                size="sm"
                onClick={() => {
                  dismissReportJob(id)
                }}
              >
                {it ? 'Chiudi avviso' : 'Dismiss'}
              </Button>
            </div>
          )
        })}
    </div>
  )
}
