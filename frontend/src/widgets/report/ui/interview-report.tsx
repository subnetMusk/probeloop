import type { InterviewReportView } from '@/entities/report'
import { useMessages } from '@/shared/i18n'
import { useLanguage } from '@/shared/lib/preferences'
import { score } from '@/shared/lib/format'
import { StatTile } from '@/shared/ui/stat-tile'
import { reportMessages } from './messages'
import { Criteria, Hero, Notes, Quotes, ReportSection, TechnicalDetails } from './report-parts'

export function InterviewReport({ view }: { view: InterviewReportView }) {
  const t = useMessages(reportMessages)
  const language = useLanguage()
  const delivery = view.delivery
  const number = (value: number | null | undefined, suffix = '') =>
    value == null ? '—' : `${score(value, language)}${suffix}`
  const percent = (value: number | null) => (value === null ? '—' : `${String(Math.round(value))}%`)
  return (
    <>
      <Hero view={view} />
      <p className="text-sm text-muted-foreground">{t.modelNote}</p>
      <ReportSection id="improvements" title={t.improvements}>
        <Notes notes={view.improvements} />
      </ReportSection>
      <ReportSection id="strengths" title={t.strengths}>
        <Notes notes={view.strengths} />
      </ReportSection>
      <ReportSection id="questions" title={t.units}>
        {view.units.map((unit) => (
          <article
            id={`question-${String(unit.number)}`}
            key={unit.id}
            className="scroll-mt-6 rounded-2xl border bg-card p-5 sm:p-6"
          >
            <div className="mb-4 flex flex-wrap items-center justify-between gap-2">
              <h3 className="font-heading text-lg font-semibold">
                {t.question(unit.number)}
                {unit.topic && (
                  <span className="ml-2 text-sm font-normal text-muted-foreground">
                    {unit.topic}
                  </span>
                )}
              </h3>
              {!unit.scored && (
                <span className="text-sm text-muted-foreground">
                  {unit.kind === 'logistics' ? t.kinds.logistics : t.kinds.unclassified} ·{' '}
                  {t.notScored}
                </span>
              )}
            </div>
            <div className="flex flex-col gap-3">
              {unit.questions.map((question) => (
                <p key={question.seq} className="text-lg leading-relaxed">
                  {question.text}
                </p>
              ))}
            </div>
            {unit.answers.map((answer) => (
              <div
                id={`answer-${String(answer.seq)}`}
                key={answer.seq}
                className="my-5 scroll-mt-6 rounded-xl bg-muted p-4"
              >
                <h4 className="mb-2 text-xs font-semibold text-foreground/75">
                  {t.answer(answer.number)}
                </h4>
                <p className="leading-relaxed whitespace-pre-wrap">{answer.text}</p>
                {answer.audio && (
                  <audio
                    controls
                    preload="none"
                    aria-label={t.answer(answer.number)}
                    src={answer.audio}
                    className="mt-3 h-9 w-full max-w-sm"
                  />
                )}
              </div>
            ))}
            {unit.scored && <Criteria criteria={unit.scores} />}
          </article>
        ))}
        {view.criteria.length > 0 && (
          <details className="rounded-xl border p-4">
            <summary className="cursor-pointer text-sm font-medium">{t.criteria}</summary>
            <div className="mt-4">
              <Criteria criteria={view.criteria} />
            </div>
          </details>
        )}
      </ReportSection>
      <ReportSection id="requirements" title={t.requirements}>
        {view.requirements.length === 0 ? (
          <p className="text-sm text-muted-foreground">{t.noNotes}</p>
        ) : (
          <div className="overflow-x-auto rounded-xl border">
            <table className="w-full text-left text-sm">
              <thead className="bg-muted">
                <tr>
                  <th scope="col" className="p-4">
                    {t.requirements}
                  </th>
                  <th scope="col" className="p-4">
                    {t.interviewCoverage}
                  </th>
                  <th scope="col" className="p-4">
                    {t.documentCoverage}
                  </th>
                </tr>
              </thead>
              <tbody>
                {view.requirements.map((row) => (
                  <tr key={row.id} className="border-t">
                    <th scope="row" className="p-4 font-normal">
                      <p className="mb-2">{row.text}</p>
                      <Quotes quotes={row.quotes} />
                    </th>
                    <td className="p-4">{row.interview ? t.coverage[row.interview] : '—'}</td>
                    <td className="p-4">{row.documents ? t.coverage[row.documents] : '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </ReportSection>
      <ReportSection id="delivery" title={t.delivery}>
        {delivery ? (
          <>
            <div className="grid grid-cols-2 gap-4 lg:grid-cols-3">
              <StatTile label={t.metrics.rate} value={number(delivery.medianRate)} unit={t.pace} />
              <StatTile label={t.metrics.latency} value={number(delivery.medianLatency, ' s')} />
              <StatTile label={t.metrics.fillers} value={number(delivery.fillersPerMinute)} />
              <StatTile label={t.metrics.pauses} value={delivery.longPauses ?? '—'} />
              <StatTile label={t.metrics.talk} value={percent(delivery.talkShare)} />
              <StatTile label={t.metrics.budget} value={percent(delivery.budgetShare)} />
            </div>
            <details className="rounded-xl border p-4">
              <summary className="cursor-pointer text-sm font-medium">{t.perAnswer}</summary>
              <div className="mt-4 overflow-x-auto">
                <table className="w-full text-left text-sm">
                  <thead>
                    <tr>
                      {[
                        t.answer(1).replace(/\s1$/, ''),
                        t.duration,
                        t.pace,
                        t.fillers,
                        t.pauses,
                        t.latency,
                      ].map((label) => (
                        <th scope="col" key={label} className="p-2">
                          {label}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {delivery.perAnswer.map((row) => (
                      <tr key={row.seq} className="border-t">
                        <th scope="row" className="p-2 font-normal">
                          <a
                            href={`#answer-${String(row.seq)}`}
                            className="text-brand-text underline"
                          >
                            {t.answer(row.answer)}
                          </a>
                        </th>
                        {[
                          number(row.duration, ' s'),
                          number(row.rate),
                          row.fillers ?? '—',
                          row.pauses ?? '—',
                          number(row.latency, ' s'),
                        ].map((value, i) => (
                          <td key={i} className="p-2 tabular-nums">
                            {value}
                          </td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </details>
          </>
        ) : (
          <p className="text-sm text-muted-foreground">{t.statuses.not_assessable}</p>
        )}
      </ReportSection>
      {view.practice.length > 0 && (
        <ReportSection id="practice" title={t.practice}>
          <Notes notes={view.practice} />
        </ReportSection>
      )}
      <TechnicalDetails
        about={view.about}
        unstable={[...view.criteria, ...view.units.flatMap((unit) => unit.scores)].some(
          (item) => item.unstable,
        )}
      />
    </>
  )
}
