import { useQuery } from '@tanstack/react-query'
import { Link } from '@tanstack/react-router'
import { CloudIcon } from 'lucide-react'
import { useState } from 'react'

import {
  INTERVIEW_TYPES,
  TYPE_COLORS,
  interviewHistoryQuery,
  interviewLabels,
  isInterviewType,
  labelOf,
} from '@/entities/interview'
import { DeleteInterview } from '@/features/delete-interview'
import type { InterviewHistoryEntry } from '@/shared/api'
import { defineMessages, useMessages } from '@/shared/i18n'
import { minutes, relativeDay } from '@/shared/lib/format'
import { usePaged } from '@/shared/lib/pagination'
import { useLanguage } from '@/shared/lib/preferences'
import { FilterPills, ListCard } from '@/shared/ui/list-card'
import { Pager } from '@/shared/ui/pager'
import { ScoreBadge } from '@/shared/ui/score-badge'

const messages = defineMessages({
  en: {
    recent: 'Recent interviews',
    all: 'History',
    viewAll: 'All interviews',
    empty: 'No interviews yet.',
    start: 'Prepare your first interview',
    noMatch: 'No interviews match these filters.',
    answers: (count: number) => (count === 1 ? '1 answer' : `${String(count)} answers`),
    deletedProfile: 'deleted profile',
    noReport: 'No report',
    unscored: 'Not scored',
    cloud: 'ChatGPT plan',
    type: 'Interview type',
    status: 'Status',
    any: 'All',
    done: 'Completed',
    open: 'Not completed',
  },
  it: {
    recent: 'Colloqui recenti',
    all: 'Storico',
    viewAll: 'Tutti i colloqui',
    empty: 'Ancora nessun colloquio.',
    start: 'Prepara il tuo primo colloquio',
    noMatch: 'Nessun colloquio corrisponde ai filtri.',
    answers: (count: number) => (count === 1 ? '1 risposta' : `${String(count)} risposte`),
    deletedProfile: 'profilo eliminato',
    noReport: 'Nessun report',
    unscored: 'Non valutato',
    cloud: 'Piano ChatGPT',
    type: 'Tipo di colloquio',
    status: 'Stato',
    any: 'Tutti',
    done: 'Conclusi',
    open: 'Non conclusi',
  },
})

function Row({ entry, manage }: { entry: InterviewHistoryEntry; manage: boolean }) {
  const t = useMessages(messages)
  const labels = useMessages(interviewLabels)
  const language = useLanguage()
  const type = labelOf(labels, 'types', entry.interview_type)
  const date = relativeDay(entry.created_at, language)
  const details = [
    date,
    entry.effective_s !== null ? minutes(entry.effective_s) : null,
    t.answers(entry.answers),
    entry.profile ? (entry.profile.name ?? t.deletedProfile) : null,
  ].filter((part): part is string => part !== null)
  const report = entry.latest_report
  return (
    <li className="flex items-center gap-2" data-testid="interview-row">
      <Link
        to="/interviews/$sessionId"
        params={{ sessionId: entry.id }}
        className="-mx-2 flex min-w-0 flex-1 items-center gap-3 rounded-lg px-2 py-2.5 hover:bg-muted/50"
      >
        <span
          aria-hidden="true"
          className="size-2.5 shrink-0 rounded-full"
          style={{
            backgroundColor: isInterviewType(entry.interview_type)
              ? TYPE_COLORS[entry.interview_type]
              : 'var(--chart-5)',
          }}
        />
        <span className="flex min-w-0 flex-1 flex-col">
          <span className="truncate font-medium">
            {type}
            <span className="font-normal text-muted-foreground">
              {' '}
              · {labelOf(labels, 'difficulties', entry.difficulty)}
            </span>
            {entry.execution_profile === 'cloud' && (
              <CloudIcon
                className="ml-1.5 inline size-3.5 text-muted-foreground"
                aria-label={t.cloud}
              />
            )}
          </span>
          <span className="truncate text-xs text-muted-foreground">{details.join(' · ')}</span>
        </span>
        {entry.status === 'ended' || entry.status === 'failed' ? (
          <ScoreBadge value={report?.overall ?? null} missing={report ? t.unscored : t.noReport} />
        ) : (
          <span className="text-sm text-muted-foreground">
            {labelOf(labels, 'statuses', entry.status)}
          </span>
        )}
      </Link>
      {manage && <DeleteInterview sessionId={entry.id} name={`${type}, ${date}`} />}
    </li>
  )
}

/**
 * The interviews, newest first, a short page at a time. With `manage`, filters by type and
 * status and a delete action on each row.
 */
export function InterviewHistory({
  pageSize,
  manage = false,
}: {
  pageSize: number
  manage?: boolean
}) {
  const t = useMessages(messages)
  const labels = useMessages(interviewLabels)
  const history = useQuery(interviewHistoryQuery)
  const [type, setType] = useState('all')
  const [status, setStatus] = useState('all')
  const entries = (history.data ?? []).filter(
    (e) =>
      (type === 'all' || e.interview_type === type) &&
      (status === 'all' || (status === 'done') === (e.status === 'ended')),
  )
  const paged = usePaged(entries, pageSize, `${type}/${status}`)
  const title = manage ? t.all : t.recent
  return (
    <ListCard
      title={title}
      action={
        !manage &&
        (history.data?.length ?? 0) > pageSize && (
          <Link to="/interviews" className="text-sm text-brand-text underline">
            {t.viewAll}
          </Link>
        )
      }
      toolbar={
        manage && (
          <div className="flex flex-wrap gap-2">
            <FilterPills
              label={t.type}
              value={type}
              onChange={setType}
              options={[
                { value: 'all', label: t.any },
                ...INTERVIEW_TYPES.map((value) => ({
                  value,
                  label: labelOf(labels, 'types', value),
                })),
              ]}
            />
            <FilterPills
              label={t.status}
              value={status}
              onChange={setStatus}
              options={[
                { value: 'all', label: t.any },
                { value: 'done', label: t.done },
                { value: 'open', label: t.open },
              ]}
            />
          </div>
        )
      }
      footer={<Pager label={title} page={paged.page} pages={paged.pages} onPage={paged.setPage} />}
    >
      {history.error && (
        <p role="alert" className="text-sm text-destructive">
          {history.error.message}
        </p>
      )}
      {history.data?.length === 0 && (
        <p className="py-6 text-center text-sm text-muted-foreground">
          {t.empty}{' '}
          <Link to="/new-interview" className="text-brand-text underline">
            {t.start}
          </Link>
        </p>
      )}
      {history.data && history.data.length > 0 && entries.length === 0 && (
        <p className="py-6 text-center text-sm text-muted-foreground">{t.noMatch}</p>
      )}
      <ul className="flex flex-col divide-y">
        {paged.items.map((entry) => (
          <Row key={entry.id} entry={entry} manage={manage} />
        ))}
      </ul>
    </ListCard>
  )
}
