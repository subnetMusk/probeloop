import { useMessages } from '@/shared/i18n'
import { accessibilityMessages } from './messages'

const ISSUES = 'https://github.com/subnetMusk/probeloop/issues'

/** The WCAG accessibility self-assessment, linked from the footer of every page. */
export function AccessibilityPage() {
  const t = useMessages(accessibilityMessages)
  return (
    <main className="mx-auto flex max-w-3xl flex-col gap-8 px-6 py-10">
      <header className="flex flex-col gap-2">
        <h1 className="text-3xl font-semibold">{t.title}</h1>
        <p className="text-muted-foreground">{t.updated}</p>
      </header>
      <section className="flex flex-col gap-2">
        <h2 className="text-xl font-semibold">{t.commitment.title}</h2>
        <p>{t.commitment.text}</p>
      </section>
      <section className="flex flex-col gap-2">
        <h2 className="text-xl font-semibold">{t.status.title}</h2>
        <p>{t.status.text}</p>
      </section>
      <section className="flex flex-col gap-2">
        <h2 className="text-xl font-semibold">{t.method.title}</h2>
        <ul className="list-disc space-y-1 pl-6">
          {t.method.items.map((item) => (
            <li key={item}>{item}</li>
          ))}
        </ul>
      </section>
      <section className="flex flex-col gap-2">
        <h2 className="text-xl font-semibold">{t.limits.title}</h2>
        <ul className="list-disc space-y-1 pl-6">
          {t.limits.items.map((item) => (
            <li key={item}>{item}</li>
          ))}
        </ul>
      </section>
      <section className="flex flex-col gap-2">
        <h2 className="text-xl font-semibold">{t.feedback.title}</h2>
        <p>
          {t.feedback.text}{' '}
          <a href={ISSUES} target="_blank" rel="noreferrer" className="text-brand-text underline">
            {t.feedback.link}
          </a>
          .
        </p>
      </section>
    </main>
  )
}
