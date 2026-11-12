import { useQuery } from '@tanstack/react-query'
import { Link } from '@tanstack/react-router'
import { FileTextIcon } from 'lucide-react'

import { cvCheckHistoryQuery, profileCvChecksQuery } from '@/entities/cv-check'
import type { CvCheckHistoryEntry } from '@/shared/api'
import { defineMessages, useMessages } from '@/shared/i18n'
import { relativeDay } from '@/shared/lib/format'
import { usePaged } from '@/shared/lib/pagination'
import { useLanguage } from '@/shared/lib/preferences'
import { ListCard, ListEmpty, ROW_HEIGHT } from '@/shared/ui/list-card'
import { Pager } from '@/shared/ui/pager'
import { ScoreBadge } from '@/shared/ui/score-badge'

const messages = defineMessages({
  en: {
    recent: 'CV checks',
    all: 'History',
    viewAll: 'All CV checks',
    empty: 'No CV checks yet.',
    ofProfile: 'CV checks of this profile',
    create: 'Check a CV',
    profile: (name: string) => `Profile: ${name}`,
    deleted: 'deleted profile',
    noOffer: 'No job offer',
    drafted: (title: string) => `Drafted offer: ${title}`,
    against: (title: string) => `Against: ${title}`,
    versions: (count: number) => `${String(count)} versions`,
    unscored: 'Not scored',
  },
  it: {
    recent: 'CV check',
    all: 'Storico',
    viewAll: 'Tutti i CV check',
    empty: 'Ancora nessun CV check.',
    ofProfile: 'CV check di questo profilo',
    create: 'Controlla un CV',
    profile: (name: string) => `Profilo: ${name}`,
    deleted: 'profilo eliminato',
    noOffer: 'Nessuna offerta',
    drafted: (title: string) => `Offerta generata: ${title}`,
    against: (title: string) => `Rispetto a: ${title}`,
    versions: (count: number) => `${String(count)} versioni`,
    unscored: 'Non valutato',
  },
})

function Row({ entry, showProfile }: { entry: CvCheckHistoryEntry; showProfile: boolean }) {
  const t = useMessages(messages)
  const language = useLanguage()
  const report = entry.latest_report
  const offer = entry.job_offer
  const against = !offer
    ? t.noOffer
    : entry.job_mode === 'generated'
      ? t.drafted(offer.title)
      : t.against(offer.filename ?? offer.title)
  const owner = showProfile && entry.profile ? t.profile(entry.profile.name ?? t.deleted) : null
  const details = [
    owner,
    against,
    relativeDay(report.created_at, language),
    report.versions > 1 ? t.versions(report.versions) : null,
  ].filter((part): part is string => part !== null)
  return (
    <li className={ROW_HEIGHT} data-testid="cv-check-row">
      <Link
        to="/cv-checks/$snapshotId"
        params={{ snapshotId: entry.snapshot_id }}
        className="-mx-2 flex h-full items-center gap-3 rounded-lg px-2 hover:bg-muted/50"
      >
        <span className="flex size-8 shrink-0 items-center justify-center rounded-md bg-muted">
          <FileTextIcon className="size-4 text-muted-foreground" aria-hidden="true" />
        </span>
        <span className="flex min-w-0 flex-1 flex-col">
          <span className="truncate font-medium">
            {entry.cv?.filename ?? entry.cv?.title ?? 'CV'}
          </span>
          <span className="truncate text-xs text-muted-foreground">{details.join(' · ')}</span>
        </span>
        <ScoreBadge value={report.overall} missing={t.unscored} />
      </Link>
    </li>
  )
}

/**
 * The CV checks, latest first, a short page at a time; each opens its own page. With
 * `profileId`, only the checks of that profile.
 */
export function CvCheckList({
  pageSize,
  full = false,
  profileId,
}: {
  pageSize: number
  full?: boolean
  profileId?: string
}) {
  const t = useMessages(messages)
  const checks = useQuery(profileId ? profileCvChecksQuery(profileId) : cvCheckHistoryQuery)
  const paged = usePaged(checks.data ?? [], pageSize)
  const title = profileId ? t.ofProfile : full ? t.all : t.recent
  return (
    <ListCard
      title={title}
      rows={full ? undefined : pageSize}
      action={
        !full &&
        !profileId &&
        (checks.data?.length ?? 0) > pageSize && (
          <Link to="/cv-checks" className="text-sm text-brand-text underline">
            {t.viewAll}
          </Link>
        )
      }
      footer={<Pager label={title} page={paged.page} pages={paged.pages} onPage={paged.setPage} />}
    >
      {checks.error && (
        <p role="alert" className="text-sm text-destructive">
          {checks.error.message}
        </p>
      )}
      {checks.data?.length === 0 && (
        <ListEmpty>
          {t.empty}{' '}
          <Link
            to="/cv-checks/new"
            search={profileId ? { profile: profileId } : {}}
            className="text-brand-text underline"
          >
            {t.create}
          </Link>
        </ListEmpty>
      )}
      <ul className="flex flex-col divide-y">
        {paged.items.map((entry) => (
          <Row key={entry.snapshot_id} entry={entry} showProfile={!profileId} />
        ))}
      </ul>
    </ListCard>
  )
}
