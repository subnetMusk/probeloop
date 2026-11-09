import { defineMessages, useMessages } from '@/shared/i18n'
import { Page, PageHeader } from '@/shared/ui/page-header'
import { ProfileList } from '@/widgets/profile-list'

const messages = defineMessages({
  en: {
    title: 'Profiles',
    subtitle:
      'Saved sets of documents: a CV, a job offer and resources. Rename them here, open one to edit its documents.',
  },
  it: {
    title: 'Profili',
    subtitle:
      'Insiemi di documenti salvati: CV, offerta e risorse. Rinominali qui, aprine uno per modificarne i documenti.',
  },
})

export function ProfilesPage() {
  const t = useMessages(messages)
  return (
    <Page>
      <PageHeader title={t.title} description={t.subtitle} />
      <ProfileList pageSize={15} manage />
    </Page>
  )
}
