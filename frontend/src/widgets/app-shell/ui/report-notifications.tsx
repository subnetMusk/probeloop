import { useQuery, useQueryClient } from '@tanstack/react-query'
import { Link } from '@tanstack/react-router'
import { CheckCircle2Icon, TriangleAlertIcon, XIcon } from 'lucide-react'

import { api, isRunning, localizeProblem } from '@/shared/api'
import { Button } from '@/shared/ui/button'
import { dismissReportJob, useReportJobs } from '@/entities/report-job'
import { useLanguage } from '@/shared/lib/preferences'
import { defineMessages, useMessages } from '@/shared/i18n'

const messages = defineMessages({
  en: {
    ready: 'Your report is ready',
    failed: 'Processing failed or unavailable',
    dismiss: 'Dismiss',
  },
  it: {
    ready: 'Il report è pronto',
    failed: 'Elaborazione non riuscita o non disponibile',
    dismiss: 'Chiudi avviso',
  },
})

export function ReportNotifications() {
  const ids = useReportJobs()
  const language = useLanguage()
  const t = useMessages(messages)
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
  // Toasts in the top right corner, below the header, over the page rather than in its flow.
  return (
    <div
      className="pointer-events-none fixed top-20 right-4 left-4 z-50 flex flex-col items-end gap-2 sm:left-auto sm:w-96"
      aria-live="polite"
    >
      {jobs.data
        ?.filter(({ job }) => !isRunning(job ?? undefined))
        .map(({ id, job }) => {
          const reportId = job?.result?.report_id
          const ready = job?.status === 'succeeded' && typeof reportId === 'string'
          return (
            <div
              key={id}
              className="pointer-events-auto flex w-full items-start gap-3 rounded-xl border bg-popover p-3 text-sm text-popover-foreground shadow-lg motion-safe:animate-in motion-safe:fade-in motion-safe:slide-in-from-right-4"
              role="status"
            >
              {ready ? (
                <CheckCircle2Icon className="mt-0.5 size-4 shrink-0 text-success" aria-hidden />
              ) : (
                <TriangleAlertIcon
                  className="mt-0.5 size-4 shrink-0 text-destructive"
                  aria-hidden
                />
              )}
              <p className="min-w-0 flex-1">
                {ready ? (
                  <Link
                    className="font-medium underline underline-offset-4"
                    to="/reports/$reportId"
                    params={{ reportId }}
                  >
                    {t.ready}
                  </Link>
                ) : (
                  <>
                    {t.failed}: {job?.error && localizeProblem(job.error, language)}
                  </>
                )}
              </p>
              <Button
                variant="ghost"
                size="icon-sm"
                className="-my-1 -mr-1"
                aria-label={t.dismiss}
                title={t.dismiss}
                onClick={() => {
                  dismissReportJob(id)
                }}
              >
                <XIcon />
              </Button>
            </div>
          )
        })}
    </div>
  )
}
