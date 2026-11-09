import { defineMessages, useMessages } from '@/shared/i18n'
import { Page, PageHeader } from '@/shared/ui/page-header'
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
    <Page>
      <PageHeader title={t.title} description={t.subtitle} />
      <CvCheckList pageSize={15} full />
    </Page>
  )
}
