import { defineMessages, useMessages } from '@/shared/i18n'
import { CvCheckList } from '@/widgets/cv-check-list'

const messages = defineMessages({
  en: {
    title: 'CV checks',
    subtitle: 'Every CV check, latest first. Open one for the original file and its reports.',
  },
  it: {
    title: 'CV check',
    subtitle:
      'Tutti i controlli del CV, dal più recente. Aprine uno per il file originale e i report.',
  },
})

export function CvChecksPage() {
  const t = useMessages(messages)
  return (
    <main className="mx-auto flex w-full max-w-5xl flex-col gap-6 px-6 py-8">
      <header className="flex flex-col gap-1">
        <h1 className="text-3xl font-semibold tracking-tight">{t.title}</h1>
        <p className="text-muted-foreground">{t.subtitle}</p>
      </header>
      <CvCheckList pageSize={15} full />
    </main>
  )
}
