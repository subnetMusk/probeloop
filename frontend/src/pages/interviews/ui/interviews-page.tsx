import { Link } from '@tanstack/react-router'
import { PlusIcon } from 'lucide-react'

import { defineMessages, useMessages } from '@/shared/i18n'
import { Button } from '@/shared/ui/button'
import { Page, PageHeader } from '@/shared/ui/page-header'
import { InterviewHistory } from '@/widgets/interview-history'

const messages = defineMessages({
  en: {
    title: 'Interviews',
    subtitle: 'Every interview, newest first. Open one for its transcript, recording and reports.',
    start: 'New interview',
  },
  it: {
    title: 'Colloqui',
    subtitle:
      'Tutti i colloqui, dal più recente. Aprine uno per trascritto, registrazione e report.',
    start: 'Nuovo colloquio',
  },
})

export function InterviewsPage() {
  const t = useMessages(messages)
  return (
    <Page>
      <PageHeader
        title={t.title}
        description={t.subtitle}
        actions={
          <Button asChild variant="outline">
            <Link to="/new-interview">
              <PlusIcon data-icon="inline-start" />
              {t.start}
            </Link>
          </Button>
        }
      />
      <InterviewHistory pageSize={15} manage />
    </Page>
  )
}
