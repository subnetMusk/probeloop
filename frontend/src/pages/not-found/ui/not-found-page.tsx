import { Link } from '@tanstack/react-router'
import { useEffect } from 'react'

import { defineMessages, useMessages } from '@/shared/i18n'
import { Button } from '@/shared/ui/button'
import { Page, PageHeader } from '@/shared/ui/page-header'

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
    <Page narrow>
      <PageHeader title={t.title} description={t.text} />
      <Button asChild className="self-start">
        <Link to="/dashboard">{t.back}</Link>
      </Button>
    </Page>
  )
}
