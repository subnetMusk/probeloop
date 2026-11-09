import { Link } from '@tanstack/react-router'
import { PlusIcon } from 'lucide-react'

import { defineMessages, useMessages } from '@/shared/i18n'
import { Button } from '@/shared/ui/button'
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
    <main className="mx-auto flex w-full max-w-5xl flex-col gap-6 px-6 py-8">
      <header className="flex flex-wrap items-end justify-between gap-4">
        <div className="flex flex-col gap-1">
          <h1 className="text-3xl font-semibold tracking-tight">{t.title}</h1>
          <p className="text-muted-foreground">{t.subtitle}</p>
        </div>
        <Button asChild variant="outline">
          <Link to="/new-interview">
            <PlusIcon data-icon="inline-start" />
            {t.start}
          </Link>
        </Button>
      </header>
      <InterviewHistory pageSize={15} manage />
    </main>
  )
}
