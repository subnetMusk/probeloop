import { useQuery } from '@tanstack/react-query'
import { useParams } from '@tanstack/react-router'

import { api } from '@/shared/api'
import { ReportContent } from '@/legacy/reports/report-content'

export function ReportPage() {
  const reportId = useParams({ strict: false }).reportId ?? ''
  const report = useQuery({ queryKey: ['report', reportId], queryFn: () => api.report(reportId) })
  const it = report.data?.language === 'it'
  return (
    <main className="mx-auto flex max-w-5xl flex-col gap-6 px-6 py-10">
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
