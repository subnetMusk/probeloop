import { useQuery } from '@tanstack/react-query'
import { Link, useParams } from '@tanstack/react-router'

import { api } from '@/api/rest'
import { Button } from '@/components/ui/button'
import { ReportContent } from '@/reports/report-content'
import { T } from '@/settings/translated-text'

export function ReportPage() {
  const { reportId } = useParams({ from: '/reports/$reportId' })
  const report = useQuery({ queryKey: ['report', reportId], queryFn: () => api.report(reportId) })
  const it = report.data?.language === 'it'
  return (
    <main className="mx-auto flex max-w-5xl flex-col gap-6 px-6 py-10">
      <Button asChild variant="ghost" className="self-start">
        <Link to="/">
          <T text={it ? 'Nuovo colloquio' : 'New interview'} />
        </Link>
      </Button>
      <h1 className="text-3xl font-semibold">
        {report.data?.kind === 'cv'
          ? it
            ? 'Revisione del CV'
            : 'CV review'
          : it
            ? 'Report del colloquio'
            : 'Interview report'}
      </h1>
      {report.error && (
        <p role="alert" className="text-destructive">
          {report.error.message}
        </p>
      )}
      {report.data && <ReportContent report={report.data} />}
    </main>
  )
}
