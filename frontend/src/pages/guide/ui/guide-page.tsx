import { Link } from '@tanstack/react-router'
import { ArrowRightIcon } from 'lucide-react'
import { useEffect } from 'react'

import { markGuideSeen } from '@/shared/lib/onboarding'
import { useLanguage } from '@/shared/lib/preferences'
import { Button } from '@/shared/ui/button'
import { Page, PageHeader } from '@/shared/ui/page-header'
import { TocLayout } from '@/shared/ui/page-toc'
import type { GuideSection } from './messages'
import { guideContent } from './messages'

function Section({ section }: { section: GuideSection }) {
  return (
    <section
      id={section.id}
      aria-labelledby={`${section.id}-title`}
      className="flex scroll-mt-6 flex-col gap-4 rounded-2xl border bg-card p-5 sm:p-6"
    >
      <h2 id={`${section.id}-title`} className="text-xl font-semibold">
        {section.title}
      </h2>
      {section.lead && <p className="text-muted-foreground">{section.lead}</p>}
      {section.steps && (
        <ol className="flex flex-col gap-4">
          {section.steps.map((step, index) => (
            <li key={step.title} className="flex gap-4">
              <span
                aria-hidden
                className="flex size-7 shrink-0 items-center justify-center rounded-full bg-brand/10 text-sm font-semibold text-brand-text"
              >
                {index + 1}
              </span>
              <div className="flex min-w-0 flex-col gap-1">
                <p className="font-medium">{step.title}</p>
                <p className="text-sm text-muted-foreground">{step.text}</p>
                {step.link && (
                  <Link
                    to={step.link.to}
                    className="mt-1 inline-flex items-center gap-1 self-start text-sm font-medium text-brand-text underline-offset-4 hover:underline"
                  >
                    {step.link.label}
                    <ArrowRightIcon className="size-3.5" aria-hidden />
                  </Link>
                )}
              </div>
            </li>
          ))}
        </ol>
      )}
      {section.points && (
        <dl className="flex flex-col gap-3">
          {section.points.map((point) => (
            <div
              key={point.term}
              className="grid gap-1 sm:grid-cols-[12rem_minmax(0,1fr)] sm:gap-4"
            >
              <dt className="font-medium">{point.term}</dt>
              <dd className="text-sm text-muted-foreground">{point.text}</dd>
            </div>
          ))}
        </dl>
      )}
    </section>
  )
}

/**
 * How the application works, for a first-time user: setup, each stage of an interview, where to
 * find things and what to do when something fails. Contextual help elsewhere links here.
 */
export function GuidePage() {
  const t = guideContent[useLanguage()]
  useEffect(() => {
    markGuideSeen() // ticks the step of the dashboard's first-run list
  }, [])
  return (
    <Page>
      <PageHeader
        title={t.title}
        description={t.description}
        actions={
          <Button asChild>
            <Link to="/new-interview">{t.start}</Link>
          </Button>
        }
      />
      <TocLayout
        label={t.toc}
        items={t.sections.map((section) => ({ id: section.id, label: section.title }))}
      >
        {t.sections.map((section) => (
          <Section key={section.id} section={section} />
        ))}
      </TocLayout>
    </Page>
  )
}
