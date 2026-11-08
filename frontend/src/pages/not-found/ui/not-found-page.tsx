import { Link } from '@tanstack/react-router'
import { useEffect } from 'react'

import { defineMessages, useMessages } from '@/shared/i18n'
import { Button } from '@/shared/ui/button'

const messages = defineMessages({
  en: {
    title: 'Page not found',
    text: 'This address does not match any page of ProbeLoop.',
    back: 'Go to the dashboard',
  },
  it: {
    title: 'Pagina non trovata',
    text: 'Questo indirizzo non corrisponde a nessuna pagina di ProbeLoop.',
    back: 'Vai alla dashboard',
  },
})

export function NotFoundPage() {
  const t = useMessages(messages)
  useEffect(() => {
    document.title = 'not-found | ProbeLoop'
  }, [])
  return (
    <main className="mx-auto flex max-w-3xl flex-col items-start gap-4 px-6 py-16">
      <h1 className="text-3xl font-semibold">{t.title}</h1>
      <p className="text-muted-foreground">{t.text}</p>
      <Button asChild>
        <Link to="/dashboard">{t.back}</Link>
      </Button>
    </main>
  )
}
