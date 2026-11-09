import { RequirementList } from '@/entities/preparation'
import type { CvReportView } from '@/entities/report'
import type { SnapshotView } from '@/shared/api'
import { useMessages } from '@/shared/i18n'
import { Button } from '@/shared/ui/button'
import { reportMessages } from './messages'
import { Checks, Criteria, Hero, Notes, ReportSection, TechnicalDetails } from './report-parts'

export function CvReport({ view, snapshot }: { view: CvReportView; snapshot?: SnapshotView }) {
  const t = useMessages(reportMessages)
  const cv = snapshot?.documents.find((document) => document.kind === 'cv')
  const original = cv ? `/api/documents/${encodeURIComponent(cv.id)}/original` : ''
  return (
    <>
      <Hero view={view} />
      <p className="text-sm text-muted-foreground">{t.modelNote}</p>
      <ReportSection id="criteria" title={t.criteria}>
        <Criteria criteria={view.criteria} />
      </ReportSection>
      <ReportSection id="requirements" title={t.requirements}>
        <RequirementList requirements={snapshot?.requirements ?? []} />
      </ReportSection>
      <ReportSection id="checks" title={t.checks}>
        <Checks checks={view.checks} />
      </ReportSection>
      <ReportSection id="improvements" title={t.improvements}>
        <Notes notes={view.improvements} />
      </ReportSection>
      <ReportSection id="strengths" title={t.strengths}>
        <Notes notes={view.strengths} />
      </ReportSection>
      <ReportSection id="rewrites" title={t.rewrites}>
        <Notes notes={view.rewrites} />
      </ReportSection>
      <ReportSection id="practice" title={t.practice}>
        <Notes notes={view.practice} />
      </ReportSection>
      <ReportSection id="original" title={t.original}>
        {cv?.has_original ? (
          <div className="flex flex-col gap-4">
            <Button asChild variant="outline" className="self-start">
              <a href={original} target="_blank" rel="noreferrer">
                {t.openOriginal}
              </a>
            </Button>
            {cv.media_type === 'application/pdf' && (
              <iframe
                src={original}
                title={t.original}
                className="h-[34rem] w-full rounded-xl border"
              />
            )}
          </div>
        ) : (
          <p className="text-sm text-muted-foreground">{t.typed}</p>
        )}
      </ReportSection>
      <TechnicalDetails about={view.about} unstable={view.criteria.some((item) => item.unstable)} />
    </>
  )
}
