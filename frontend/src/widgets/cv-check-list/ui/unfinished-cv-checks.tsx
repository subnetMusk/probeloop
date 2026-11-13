import { useQuery } from '@tanstack/react-query'
import { Link } from '@tanstack/react-router'
import { FileTextIcon, Loader2Icon, XIcon } from 'lucide-react'

import { forgetCvCheckPreparation } from '@/entities/cv-check'
import { api, isRunning } from '@/shared/api'
import type { DocumentView } from '@/shared/api'
import { defineMessages, useMessages } from '@/shared/i18n'
import { relativeDay } from '@/shared/lib/format'
import { useLanguage } from '@/shared/lib/preferences'
import { Alert, AlertDescription } from '@/shared/ui/alert'
import { Button } from '@/shared/ui/button'
import { ListCard, ROW_HEIGHT } from '@/shared/ui/list-card'
import { useUnfinishedCvChecks } from '../model/unfinished'
import type { UnfinishedCheck } from '../model/unfinished'

const messages = defineMessages({
  en: {
    title: 'In progress',
    analysing: (percent: string) => `Analysing the documents · ${percent}`,
    review: 'Analysis ready to review',
    failed: 'The analysis failed',
    checking: (percent: string) => `Checking the CV · ${percent}`,
    stopped: 'The CV check did not finish',
    remove: (name: string) => `Remove ${name} from the list`,
    notice: (count: number) =>
      count === 1
        ? 'A CV check you started is not finished.'
        : `${String(count)} CV checks you started are not finished.`,
  },
  it: {
    title: 'In corso',
    analysing: (percent: string) => `Analisi dei documenti in corso · ${percent}`,
    review: 'Analisi pronta da rivedere',
    failed: 'Analisi non riuscita',
    checking: (percent: string) => `Controllo del CV in corso · ${percent}`,
    stopped: 'Il controllo del CV non è terminato',
    remove: (name: string) => `Togli ${name} dall’elenco`,
    notice: (count: number) =>
      count === 1
        ? 'Un CV check che hai iniziato non è finito.'
        : `${String(count)} CV check che hai iniziato non sono finiti.`,
  },
})

const percent = (progress: number | undefined) => `${String(Math.round((progress ?? 0) * 100))}%`
const cvName = (documents: DocumentView[] | undefined) => {
  const cv = documents?.find((d) => d.kind === 'cv')
  return cv?.filename ?? cv?.title ?? 'CV'
}

function Row({ check }: { check: UnfinishedCheck }) {
  const t = useMessages(messages)
  const language = useLanguage()
  // A review started elsewhere has no remembered preparation: its context names the CV.
  const snapshot = useQuery({
    queryKey: ['snapshot', check.kind === 'review' ? check.snapshotId : ''],
    queryFn: () => api.snapshot(check.kind === 'review' ? check.snapshotId : ''),
    enabled: check.kind === 'review' && check.preparation === null,
    staleTime: Infinity,
  })
  const documents =
    check.kind === 'analysis'
      ? check.preparation.documents
      : (check.preparation?.documents ?? snapshot.data?.documents)
  const name = cvName(documents)
  const busy =
    check.kind === 'analysis' ? check.state === 'analysing' : isRunning(check.job ?? undefined)
  const state =
    check.kind === 'analysis'
      ? check.state === 'analysing'
        ? t.analysing(percent(check.preparation.analysis?.progress))
        : check.state === 'failed'
          ? t.failed
          : t.review
      : check.job
        ? t.checking(percent(check.job.progress))
        : t.stopped
  const Icon = busy ? Loader2Icon : FileTextIcon
  const preparationId = check.kind === 'analysis' ? check.preparation.id : check.preparation?.id
  return (
    <li className={`${ROW_HEIGHT} flex items-center gap-2`} data-testid="unfinished-cv-check">
      <Link
        {...(check.kind === 'analysis'
          ? {
              to: '/cv-checks/new/$preparationId',
              params: { preparationId: check.preparation.id },
            }
          : { to: '/cv-checks/$snapshotId', params: { snapshotId: check.snapshotId } })}
        className="-mx-2 flex h-full min-w-0 flex-1 items-center gap-3 rounded-lg px-2 hover:bg-muted/50"
      >
        <span className="flex size-8 shrink-0 items-center justify-center rounded-md bg-muted">
          <Icon
            className={`size-4 text-muted-foreground ${busy ? 'animate-spin' : ''}`}
            aria-hidden="true"
          />
        </span>
        <span className="flex min-w-0 flex-1 flex-col">
          <span className="truncate font-medium">{name}</span>
          <span className="truncate text-xs text-muted-foreground">
            {state} · {relativeDay(check.at, language)}
          </span>
        </span>
      </Link>
      {!busy && preparationId && (
        <Button
          type="button"
          variant="ghost"
          size="icon"
          aria-label={t.remove(name)}
          title={t.remove(name)}
          onClick={() => {
            forgetCvCheckPreparation(preparationId)
          }}
        >
          <XIcon aria-hidden="true" />
        </Button>
      )}
    </li>
  )
}

/** The CV checks started and not finished, latest first; shown only when there are some. */
export function UnfinishedCvChecks() {
  const t = useMessages(messages)
  const checks = useUnfinishedCvChecks()
  if (checks.length === 0) return null
  return (
    <ListCard title={t.title}>
      <ul className="flex flex-col divide-y">
        {checks.map((check) => (
          <Row
            key={check.kind === 'analysis' ? check.preparation.id : check.snapshotId}
            check={check}
          />
        ))}
      </ul>
    </ListCard>
  )
}

/** A notice, where a new CV check starts, with the unfinished ones to open directly. */
export function UnfinishedCvChecksNotice() {
  const t = useMessages(messages)
  const checks = useUnfinishedCvChecks()
  if (checks.length === 0) return null
  return (
    <Alert>
      <AlertDescription className="flex flex-col gap-1">
        <p>{t.notice(checks.length)}</p>
        <ul className="flex w-full flex-col divide-y">
          {checks.map((check) => (
            <Row
              key={check.kind === 'analysis' ? check.preparation.id : check.snapshotId}
              check={check}
            />
          ))}
        </ul>
      </AlertDescription>
    </Alert>
  )
}
