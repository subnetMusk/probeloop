import { useQuery } from '@tanstack/react-query'
import { Link } from '@tanstack/react-router'
import { ArrowRightIcon, PlayIcon } from 'lucide-react'

import { profilesQuery } from '@/entities/profile'
import { DeleteProfile, RenameProfile } from '@/features/manage-profile'
import { useStartWithProfile } from '@/features/select-profile'
import type { ProfileView } from '@/shared/api'
import { defineMessages, useMessages } from '@/shared/i18n'
import { relativeDay } from '@/shared/lib/format'
import { usePaged } from '@/shared/lib/pagination'
import { useLanguage } from '@/shared/lib/preferences'
import { Button } from '@/shared/ui/button'
import { ListCard } from '@/shared/ui/list-card'
import { Pager } from '@/shared/ui/pager'

const messages = defineMessages({
  en: {
    recent: 'Resource profiles',
    all: 'Saved profiles',
    viewAll: 'All profiles',
    empty: 'No profiles yet. Choose “New profile” when you prepare an interview.',
    noCv: 'no CV',
    noOffer: 'no job offer',
    resources: (count: number) => (count === 1 ? '1 resource' : `${String(count)} resources`),
    updated: (when: string) => `updated ${when}`,
    use: (name: string) => `New interview with ${name}`,
    open: (name: string) => `Open ${name}`,
  },
  it: {
    recent: 'Profili delle risorse',
    all: 'Profili salvati',
    viewAll: 'Tutti i profili',
    empty: 'Ancora nessun profilo. Scegli «Nuovo profilo» quando prepari un colloquio.',
    noCv: 'nessun CV',
    noOffer: 'nessuna offerta',
    resources: (count: number) => (count === 1 ? '1 risorsa' : `${String(count)} risorse`),
    updated: (when: string) => `aggiornato ${when}`,
    use: (name: string) => `Nuovo colloquio con ${name}`,
    open: (name: string) => `Apri ${name}`,
  },
})

function Row({ profile, manage }: { profile: ProfileView; manage: boolean }) {
  const t = useMessages(messages)
  const language = useLanguage()
  const start = useStartWithProfile()
  const parts = [
    profile.cv ? (profile.cv.filename ?? profile.cv.title) : t.noCv,
    profile.job_offer ? (profile.job_offer.filename ?? profile.job_offer.title) : t.noOffer,
    t.resources(profile.resources.length),
    manage ? t.updated(relativeDay(profile.updated_at, language)) : null,
  ].filter((part): part is string => part !== null)
  return (
    <li className="flex items-center gap-2 py-2.5" data-testid="profile-row">
      <div className="flex min-w-0 flex-1 flex-col">
        <RenameProfile profile={profile} className="truncate font-medium" />
        <span className="truncate text-xs text-muted-foreground">{parts.join(' · ')}</span>
      </div>
      <Button
        type="button"
        variant="ghost"
        size="icon-sm"
        aria-label={t.use(profile.name)}
        title={t.use(profile.name)}
        onClick={() => {
          start(profile)
        }}
      >
        <PlayIcon />
      </Button>
      <Button variant="ghost" size="icon-sm" asChild>
        <Link
          to="/profiles/$profileId"
          params={{ profileId: profile.id }}
          aria-label={t.open(profile.name)}
          title={t.open(profile.name)}
        >
          <ArrowRightIcon />
        </Link>
      </Button>
      {manage && <DeleteProfile profile={profile} />}
    </li>
  )
}

/** The saved profiles, most recently updated first, renamed in place. */
export function ProfileList({ pageSize, manage = false }: { pageSize: number; manage?: boolean }) {
  const t = useMessages(messages)
  const profiles = useQuery(profilesQuery)
  const sorted = [...(profiles.data ?? [])].sort((a, b) => b.updated_at - a.updated_at)
  const paged = usePaged(sorted, pageSize)
  const title = manage ? t.all : t.recent
  return (
    <ListCard
      title={title}
      action={
        !manage &&
        sorted.length > pageSize && (
          <Link to="/profiles" className="text-sm text-brand-text underline">
            {t.viewAll}
          </Link>
        )
      }
      footer={<Pager label={title} page={paged.page} pages={paged.pages} onPage={paged.setPage} />}
    >
      {profiles.error && (
        <p role="alert" className="text-sm text-destructive">
          {profiles.error.message}
        </p>
      )}
      {profiles.data?.length === 0 && (
        <p className="py-4 text-sm text-muted-foreground">{t.empty}</p>
      )}
      <ul className="flex flex-col divide-y">
        {paged.items.map((profile) => (
          <Row key={profile.id} profile={profile} manage={manage} />
        ))}
      </ul>
    </ListCard>
  )
}
