import { useQuery } from '@tanstack/react-query'
import { Link } from '@tanstack/react-router'
import { FileTextIcon } from 'lucide-react'

import { cvCheckHistoryQuery } from '@/entities/cv-check'
import type { CvCheckHistoryEntry } from '@/shared/api'
import { defineMessages, useMessages } from '@/shared/i18n'
import { relativeDay } from '@/shared/lib/format'
import { usePaged } from '@/shared/lib/pagination'
import { useLanguage } from '@/shared/lib/preferences'
import { ListCard } from '@/shared/ui/list-card'
import { Pager } from '@/shared/ui/pager'
import { ScoreBadge } from '@/shared/ui/score-badge'

const messages = defineMessages({
  en: {
    recent: 'CV checks',
    all: 'History',
    viewAll: 'All CV checks',
    empty: 'No CV checks yet. You can check your CV in the last step of a new interview.',
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
    empty:
      'Ancora nessun CV check. Puoi controllare il CV nell’ultimo passo di un nuovo colloquio.',
    noOffer: 'Nessuna offerta',
    drafted: (title: string) => `Offerta generata: ${title}`,
    against: (title: string) => `Rispetto a: ${title}`,
    versions: (count: number) => `${String(count)} versioni`,
    unscored: 'Non valutato',
  },
})

function Row({ entry }: { entry: CvCheckHistoryEntry }) {
  const t = useMessages(messages)
  const language = useLanguage()
  const report = entry.latest_report
  const offer = entry.job_offer
  const against = !offer
    ? t.noOffer
    : entry.job_mode === 'generated'
      ? t.drafted(offer.title)
      : t.against(offer.filename ?? offer.title)
  const details = [
    against,
    relativeDay(report.created_at, language),
    report.versions > 1 ? t.versions(report.versions) : null,
  ].filter((part): part is string => part !== null)
  return (
    <li data-testid="cv-check-row">
      <Link
        to="/cv-checks/$snapshotId"
        params={{ snapshotId: entry.snapshot_id }}
        className="-mx-2 flex items-center gap-3 rounded-lg px-2 py-2.5 hover:bg-muted/50"
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

/** The CV checks, latest first, a short page at a time; each opens its own page. */
export function CvCheckList({ pageSize, full = false }: { pageSize: number; full?: boolean }) {
  const t = useMessages(messages)
  const checks = useQuery(cvCheckHistoryQuery)
  const paged = usePaged(checks.data ?? [], pageSize)
  const title = full ? t.all : t.recent
  return (
    <ListCard
      title={title}
      action={
        !full &&
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
      {checks.data?.length === 0 && <p className="py-4 text-sm text-muted-foreground">{t.empty}</p>}
      <ul className="flex flex-col divide-y">
        {paged.items.map((entry) => (
          <Row key={entry.snapshot_id} entry={entry} />
        ))}
      </ul>
    </ListCard>
  )
}
