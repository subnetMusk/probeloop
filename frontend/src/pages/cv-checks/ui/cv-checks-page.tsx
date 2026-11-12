import { Link } from '@tanstack/react-router'
import { PlusIcon } from 'lucide-react'

import { defineMessages, useMessages } from '@/shared/i18n'
import { Button } from '@/shared/ui/button'
import { Page, PageHeader } from '@/shared/ui/page-header'
import { CvCheckList } from '@/widgets/cv-check-list'

const messages = defineMessages({
  en: {
    title: 'CV checks',
    subtitle:
      'Every CV check, latest first. Check a CV from a saved profile or from documents you add here.',
    create: 'New CV check',
  },
  it: {
    title: 'CV check',
    subtitle:
      'Tutti i controlli del CV, dal più recente. Controlla un CV da un profilo salvato o da documenti che aggiungi qui.',
    create: 'Nuovo CV check',
  },
})

export function CvChecksPage() {
  const t = useMessages(messages)
  return (
    <Page>
      <PageHeader
        title={t.title}
        description={t.subtitle}
        actions={
          <Button asChild variant="outline">
            <Link to="/cv-checks/new">
              <PlusIcon data-icon="inline-start" />
              {t.create}
            </Link>
          </Button>
        }
      />
      <CvCheckList pageSize={15} full />
    </Page>
  )
}
