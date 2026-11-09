import { useQuery } from '@tanstack/react-query'
import { Link, useParams } from '@tanstack/react-router'

import { interviewHistoryQuery, interviewLabels, labelOf } from '@/entities/interview'
import { toCvReportView, toInterviewReportView } from '@/entities/report'
import { api, sessionFile } from '@/shared/api'
import { useMessages } from '@/shared/i18n'
import { minutes, shortDate } from '@/shared/lib/format'
import { useLanguage } from '@/shared/lib/preferences'
import { Badge } from '@/shared/ui/badge'
import { Button } from '@/shared/ui/button'
import { Page, PageHeader } from '@/shared/ui/page-header'
import { CvReport, InterviewReport, reportMessages } from '@/widgets/report'

export function ReportPage() {
  const t = useMessages(reportMessages)
  const labels = useMessages(interviewLabels)
  const language = useLanguage()
  const reportId = useParams({ strict: false }).reportId ?? ''
  const report = useQuery({ queryKey: ['report', reportId], queryFn: () => api.report(reportId) })
  const sessionId = report.data?.session_id ?? ''
  const snapshotId = report.data?.snapshot_id ?? ''
  const session = useQuery({
    queryKey: ['session', sessionId],
    queryFn: () => api.session(sessionId),
    enabled: !!sessionId,
  })
  const history = useQuery({ ...interviewHistoryQuery, enabled: !!sessionId })
  const snapshot = useQuery({
    queryKey: ['snapshot', snapshotId],
    queryFn: () => api.snapshot(snapshotId),
    enabled: !!snapshotId && report.data?.kind === 'cv',
  })
  const metadata = history.data?.find((item) => item.id === sessionId)
  const data = report.data
  if (!data)
    return (
      <Page>
        <p role={report.error ? 'alert' : 'status'}>{report.error?.message ?? t.loading}</p>
      </Page>
    )
  return (
    <Page>
      <PageHeader
        eyebrow={t.version(data.version)}
        title={data.kind === 'cv' ? t.cv : t.interview}
        description={
          data.kind === 'cv'
            ? shortDate(data.created_at, language)
            : [
                metadata && labelOf(labels, 'types', metadata.interview_type),
                shortDate(metadata?.created_at ?? data.created_at, language),
                metadata?.effective_s != null && minutes(metadata.effective_s),
              ]
                .filter(Boolean)
                .join(' · ')
        }
        actions={
          <>
            {(['md', 'json', 'pdf'] as const).map((format) => (
              <Button key={format} asChild size="sm" variant="outline">
                <a href={`/api/reports/${encodeURIComponent(data.id)}/export/${format}`} download>
                  {format.toUpperCase()}
                </a>
              </Button>
            ))}
            {sessionId && (
              <>
                <Button asChild variant="outline" size="sm">
                  <Link to="/interviews/$sessionId" params={{ sessionId }}>
                    {t.transcript}
                  </Link>
                </Button>
                {session.data?.turns.some((turn) => turn.audio) && (
                  <Button asChild variant="outline" size="sm">
                    <a href={sessionFile(sessionId, 'audio/interview.wav')} download>
                      {t.recording}
                    </a>
                  </Button>
                )}
              </>
            )}
          </>
        }
      >
        {metadata?.execution_profile && (
          <Badge variant="outline" className="self-start">
            {labelOf(labels, 'execution', metadata.execution_profile)}
          </Badge>
        )}
      </PageHeader>
      <div data-testid="report-content" className="flex flex-col gap-8">
        {(session.error ?? snapshot.error) && (
          <p role="alert">{(session.error ?? snapshot.error)?.message}</p>
        )}
        {data.kind === 'cv' ? (
          snapshot.isPending && snapshotId ? (
            <p role="status">{t.loading}</p>
          ) : (
            <CvReport view={toCvReportView(data)} snapshot={snapshot.data} />
          )
        ) : session.isPending && sessionId ? (
          <p role="status">{t.loading}</p>
        ) : (
          <InterviewReport view={toInterviewReportView(data, session.data)} />
        )}
      </div>
      <Button asChild variant="outline" className="self-start">
        {data.kind === 'cv' ? (
          <Link to="/cv-checks/$snapshotId" params={{ snapshotId }}>
            {t.backCv}
          </Link>
        ) : (
          <Link to="/interviews/$sessionId" params={{ sessionId }}>
            {t.back}
          </Link>
        )}
      </Button>
    </Page>
  )
}
