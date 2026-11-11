import { useMessages } from '@/shared/i18n'
import { Page, PageHeader } from '@/shared/ui/page-header'
import { TocLayout } from '@/shared/ui/page-toc'
import { accessibilityMessages } from './messages'

const ISSUES = 'https://github.com/subnetMusk/probeloop/issues'

/** The WCAG accessibility self-assessment, linked from the footer of every page. */
export function AccessibilityPage() {
  const t = useMessages(accessibilityMessages)
  return (
    <Page>
      <PageHeader title={t.title} description={t.updated} />
      <TocLayout label={t.toc}>
        <section id="commitment" className="flex scroll-mt-6 flex-col gap-2">
          <h2 className="text-xl font-semibold">{t.commitment.title}</h2>
          <p>{t.commitment.text}</p>
        </section>
        <section id="status" className="flex scroll-mt-6 flex-col gap-2">
          <h2 className="text-xl font-semibold">{t.status.title}</h2>
          <p>{t.status.text}</p>
        </section>
        <section id="method" className="flex scroll-mt-6 flex-col gap-2">
          <h2 className="text-xl font-semibold">{t.method.title}</h2>
          <ul className="list-disc space-y-1 pl-6">
            {t.method.items.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        </section>
        <section id="limits" className="flex scroll-mt-6 flex-col gap-2">
          <h2 className="text-xl font-semibold">{t.limits.title}</h2>
          <ul className="list-disc space-y-1 pl-6">
            {t.limits.items.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        </section>
        <section id="feedback" className="flex scroll-mt-6 flex-col gap-2">
          <h2 className="text-xl font-semibold">{t.feedback.title}</h2>
          <p>
            {t.feedback.text}{' '}
            <a href={ISSUES} target="_blank" rel="noreferrer" className="text-brand-text underline">
              {t.feedback.link}
            </a>
            .
          </p>
        </section>
      </TocLayout>
    </Page>
  )
}
