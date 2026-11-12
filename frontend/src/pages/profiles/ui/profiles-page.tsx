import { Link } from '@tanstack/react-router'
import { PlusIcon } from 'lucide-react'

import { defineMessages, useMessages } from '@/shared/i18n'
import { Button } from '@/shared/ui/button'
import { Page, PageHeader } from '@/shared/ui/page-header'
import { ProfileList } from '@/widgets/profile-list'

const messages = defineMessages({
  en: {
    title: 'Profiles',
    subtitle:
      'Saved sets of documents: a CV, a job offer and resources. Rename them here, open one to edit its documents or check its CV.',
    create: 'New profile',
  },
  it: {
    title: 'Profili',
    subtitle:
      'Insiemi di documenti salvati: CV, offerta e risorse. Rinominali qui, aprine uno per modificarne i documenti o controllarne il CV.',
    create: 'Nuovo profilo',
  },
})

export function ProfilesPage() {
  const t = useMessages(messages)
  return (
    <Page>
      <PageHeader
        title={t.title}
        description={t.subtitle}
        actions={
          <Button asChild variant="outline">
            <Link to="/profiles/new">
              <PlusIcon data-icon="inline-start" />
              {t.create}
            </Link>
          </Button>
        }
      />
      <ProfileList pageSize={15} manage />
    </Page>
  )
}
