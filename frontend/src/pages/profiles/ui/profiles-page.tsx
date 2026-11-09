import { defineMessages, useMessages } from '@/shared/i18n'
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
    <main className="mx-auto flex w-full max-w-5xl flex-col gap-6 px-6 py-8">
      <header className="flex flex-col gap-1">
        <h1 className="text-3xl font-semibold tracking-tight">{t.title}</h1>
        <p className="text-muted-foreground">{t.subtitle}</p>
      </header>
      <ProfileList pageSize={15} manage />
    </main>
  )
}
