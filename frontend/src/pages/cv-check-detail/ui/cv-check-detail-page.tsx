import { useQuery } from '@tanstack/react-query'
import { Link, useNavigate, useParams } from '@tanstack/react-router'
import { DownloadIcon, ExternalLinkIcon } from 'lucide-react'
import { useState } from 'react'

import { profilesQuery } from '@/entities/profile'
import { toCvReportView } from '@/entities/report'
import { CvCheck } from '@/features/check-cv'
import { DeleteCvCheck, ProfileFromCheck } from '@/features/manage-cv-check'
import { api } from '@/shared/api'
import type { DocumentView } from '@/shared/api'
import { defineMessages, useMessages } from '@/shared/i18n'
import { score, shortDate } from '@/shared/lib/format'
import { useLanguage } from '@/shared/lib/preferences'
import { Button } from '@/shared/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/shared/ui/card'
import { PAGE_TITLE, Page, PageHeader } from '@/shared/ui/page-header'
import { TocLayout } from '@/shared/ui/page-toc'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/shared/ui/select'
import { CvReport } from '@/widgets/report'

const messages = defineMessages({
  en: {
    eyebrow: 'CV check',
    notFound: 'This CV check does not exist.',
    loading: 'Loading…',
    approved: (date: string) => `Context approved on ${date}`,
    cv: 'Your CV',
    offer: 'Job offer',
    generated: 'Drafted from your description',
    noOffer: 'Checked without a job offer.',
    open: 'Open the original',
    download: 'Download the original',
    preview: (name: string) => `Preview of ${name}`,
    typed: 'Typed text: there is no original file.',
    text: 'Show the extracted text',
    version: 'Version',
    versionOption: (version: number, date: string, result: string) =>
      `Version ${String(version)} · ${date} · ${result}`,
    unscored: 'not scored',
    noVersions: 'No CV report yet: it appears here when the check ends.',
    profile: 'Profile',
    documents: 'Documents of the check',
    report: 'CV report',
    toc: 'On this page',
  },
  it: {
    eyebrow: 'CV check',
    notFound: 'Questo CV check non esiste.',
    loading: 'Caricamento…',
    approved: (date: string) => `Contesto approvato il ${date}`,
    cv: 'Il tuo CV',
    offer: 'Offerta di lavoro',
    generated: 'Generata dalla tua descrizione',
    noOffer: 'Controllato senza offerta di lavoro.',
    open: 'Apri l’originale',
    download: 'Scarica l’originale',
    preview: (name: string) => `Anteprima di ${name}`,
    typed: 'Testo digitato: non c’è un file originale.',
    text: 'Mostra il testo estratto',
    version: 'Versione',
    versionOption: (version: number, date: string, result: string) =>
      `Versione ${String(version)} · ${date} · ${result}`,
    unscored: 'non valutato',
    noVersions: 'Ancora nessun report del CV: compare qui al termine del controllo.',
    profile: 'Profilo',
    documents: 'Documenti del controllo',
    report: 'Report del CV',
    toc: 'In questa pagina',
  },
})

const originalUrl = (id: string) => `/api/documents/${encodeURIComponent(id)}/original`

/** A document of the check: the original file (a PDF previews in place) and its text. */
function DocumentCard({
  title,
  document,
  note,
  preview,
}: {
  title: string
  document: DocumentView
  note?: string
  preview: boolean
}) {
  const t = useMessages(messages)
  const [open, setOpen] = useState(false)
  const text = useQuery({
    queryKey: ['document-text', document.id],
    queryFn: () => api.documentText(document.id),
    enabled: open,
    staleTime: Infinity,
  })
  const name = document.filename ?? document.title
  const pdf = document.has_original && document.media_type === 'application/pdf'
  return (
    <Card>
      <CardHeader className="flex flex-wrap items-start justify-between gap-3">
        <div className="flex min-w-0 flex-col gap-1">
          <CardTitle role="heading" aria-level={2}>
            {title}
          </CardTitle>
          <CardDescription className="truncate">
            {note ? `${name} · ${note}` : name}
          </CardDescription>
        </div>
        {document.has_original && (
          <Button asChild variant="outline" size="sm">
            <a href={originalUrl(document.id)} target="_blank" rel="noreferrer">
              {pdf ? (
                <ExternalLinkIcon data-icon="inline-start" />
              ) : (
                <DownloadIcon data-icon="inline-start" />
              )}
              {pdf ? t.open : t.download}
            </a>
          </Button>
        )}
      </CardHeader>
      <CardContent className="flex flex-col gap-3">
        {preview && pdf && (
          <iframe
            src={originalUrl(document.id)}
            title={t.preview(name)}
            className="h-[34rem] w-full rounded-lg border bg-muted"
          />
        )}
        {!document.has_original && <p className="text-sm text-muted-foreground">{t.typed}</p>}
        <details
          className="text-sm"
          onToggle={(event) => {
            setOpen(event.currentTarget.open)
          }}
        >
          <summary className="cursor-pointer text-muted-foreground hover:text-foreground">
            {t.text}
          </summary>
          <pre className="mt-2 max-h-80 overflow-y-auto rounded-lg bg-muted/50 p-3 font-sans text-sm whitespace-pre-wrap">
            {text.data?.text ?? (text.isPending ? t.loading : text.error?.message)}
          </pre>
        </details>
      </CardContent>
    </Card>
  )
}

/**
 * One CV check: the selected version of its report in full, the controls to check again or pick
 * an earlier version, and the documents it was made from.
 */
export function CvCheckDetailPage() {
  const t = useMessages(messages)
  const language = useLanguage()
  const { snapshotId } = useParams({ from: '/cv-checks/$snapshotId/' })
  const snapshot = useQuery({
    queryKey: ['snapshot', snapshotId],
    queryFn: () => api.snapshot(snapshotId),
    staleTime: Infinity,
  })
  const reports = useQuery({
    queryKey: ['cv-reviews', snapshotId],
    queryFn: () => api.cvReviews(snapshotId),
  })
  const execution = useQuery({ queryKey: ['execution-profile'], queryFn: api.executionProfile })
  const profiles = useQuery(profilesQuery)
  const navigate = useNavigate()
  // No choice follows the latest version, including one that a new check has just added.
  const [chosen, setChosen] = useState<string | null>(null)
  const ownerId = reports.data?.at(-1)?.profile_id ?? null
  const owner = profiles.data?.find((p) => p.id === ownerId)
  const unowned = reports.data !== undefined && reports.data.every((r) => !r.profile_id)
  if (snapshot.isPending) return <Page>{t.loading}</Page>
  if (!snapshot.data)
    return (
      <Page>
        <p role="alert">{t.notFound}</p>
      </Page>
    )
  const cv = snapshot.data.documents.find((d) => d.kind === 'cv')
  const offer = snapshot.data.documents.find((d) => d.kind === 'job_offer')
  const shown = reports.data?.find((r) => r.id === chosen) ?? reports.data?.at(-1)
  return (
    <Page>
      <PageHeader
        eyebrow={t.eyebrow}
        title={<h1 className={`${PAGE_TITLE} truncate`}>{cv?.filename ?? cv?.title ?? 'CV'}</h1>}
        description={`${offer ? (offer.filename ?? offer.title) : t.noOffer} · ${t.approved(
          shortDate(snapshot.data.created_at, language),
        )}`}
        actions={
          <>
            {unowned && <ProfileFromCheck snapshotId={snapshotId} />}
            <DeleteCvCheck
              snapshotId={snapshotId}
              onDeleted={() => void navigate({ to: '/cv-checks', replace: true })}
            />
          </>
        }
      >
        {owner && (
          <p className="text-sm">
            {t.profile}:{' '}
            <Link
              to="/profiles/$profileId"
              params={{ profileId: owner.id }}
              className="text-brand-text underline"
            >
              {owner.name}
            </Link>
          </p>
        )}
      </PageHeader>
      <div className="grid items-start gap-4 lg:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
        {execution.data && (
          <CvCheck
            snapshotId={snapshotId}
            language={language}
            execution={execution.data.profile}
            summary={false}
          />
        )}
        <Card>
          <CardHeader>
            <CardTitle role="heading" aria-level={2}>
              {t.report}
            </CardTitle>
          </CardHeader>
          <CardContent className="flex flex-col gap-3">
            {reports.data?.length === 0 && (
              <p className="text-sm text-muted-foreground">{t.noVersions}</p>
            )}
            {shown && reports.data && (
              <>
                <div className="flex flex-col gap-2">
                  <label htmlFor="cv-check-version" className="text-sm font-medium">
                    {t.version}
                  </label>
                  <Select
                    value={shown.id}
                    onValueChange={(id) => {
                      setChosen(id === reports.data.at(-1)?.id ? null : id)
                    }}
                  >
                    <SelectTrigger id="cv-check-version" className="w-full">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      {reports.data.toReversed().map((report) => (
                        <SelectItem key={report.id} value={report.id}>
                          {t.versionOption(
                            report.version,
                            shortDate(report.created_at, language),
                            report.overall === null
                              ? t.unscored
                              : `${score(report.overall, language)} / 100`,
                          )}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
                <div className="flex flex-wrap gap-2">
                  {(['md', 'json', 'pdf'] as const).map((format) => (
                    <Button key={format} asChild size="sm" variant="outline">
                      <a
                        href={`/api/reports/${encodeURIComponent(shown.id)}/export/${format}`}
                        download
                      >
                        {format.toUpperCase()}
                      </a>
                    </Button>
                  ))}
                </div>
              </>
            )}
          </CardContent>
        </Card>
      </div>
      {shown && (
        <TocLayout label={t.toc}>
          <div data-testid="report-content" className="flex flex-col gap-8">
            <CvReport view={toCvReportView(shown)} snapshot={snapshot.data} />
          </div>
        </TocLayout>
      )}
      <details className="group rounded-2xl border bg-card" open={shown ? undefined : true}>
        <summary className="cursor-pointer px-5 py-4 font-heading font-semibold">
          {t.documents}
        </summary>
        <div className="grid items-start gap-6 px-5 pb-5 lg:grid-cols-2">
          {cv && <DocumentCard title={t.cv} document={cv} preview={!shown} />}
          {offer && (
            <DocumentCard
              title={t.offer}
              document={offer}
              note={snapshot.data.job_mode === 'generated' ? t.generated : undefined}
              preview={false}
            />
          )}
        </div>
      </details>
    </Page>
  )
}
