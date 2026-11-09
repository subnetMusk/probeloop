import { useQuery } from '@tanstack/react-query'
import { Link, useParams } from '@tanstack/react-router'
import { DownloadIcon, ExternalLinkIcon } from 'lucide-react'
import { useState } from 'react'

import { CvCheck } from '@/features/check-cv'
import { api } from '@/shared/api'
import type { DocumentView } from '@/shared/api'
import { defineMessages, useMessages } from '@/shared/i18n'
import { score, shortDate } from '@/shared/lib/format'
import { useLanguage } from '@/shared/lib/preferences'
import { Button } from '@/shared/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/shared/ui/card'
import { PAGE_TITLE, Page, PageHeader } from '@/shared/ui/page-header'

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
    versions: 'Versions',
    version: (version: number, date: string) => `Version ${String(version)} · ${date}`,
    unscored: 'not scored',
    noVersions: 'No CV report yet.',
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
    versions: 'Versioni',
    version: (version: number, date: string) => `Versione ${String(version)} · ${date}`,
    unscored: 'non valutato',
    noVersions: 'Ancora nessun report del CV.',
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

/** One CV check: the original CV, the job offer, the latest review and every version. */
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
  if (snapshot.isPending) return <Page>{t.loading}</Page>
  if (!snapshot.data)
    return (
      <Page>
        <p role="alert">{t.notFound}</p>
      </Page>
    )
  const cv = snapshot.data.documents.find((d) => d.kind === 'cv')
  const offer = snapshot.data.documents.find((d) => d.kind === 'job_offer')
  return (
    <Page>
      <PageHeader
        eyebrow={t.eyebrow}
        title={<h1 className={`${PAGE_TITLE} truncate`}>{cv?.filename ?? cv?.title ?? 'CV'}</h1>}
        description={`${offer ? (offer.filename ?? offer.title) : t.noOffer} · ${t.approved(
          shortDate(snapshot.data.created_at, language),
        )}`}
      />
      <div className="grid items-start gap-6 lg:grid-cols-5">
        <div className="flex flex-col gap-6 lg:col-span-3">
          {cv && <DocumentCard title={t.cv} document={cv} preview />}
          {offer && (
            <DocumentCard
              title={t.offer}
              document={offer}
              note={snapshot.data.job_mode === 'generated' ? t.generated : undefined}
              preview={false}
            />
          )}
        </div>
        <div className="flex flex-col gap-6 lg:col-span-2">
          {execution.data && (
            <CvCheck
              snapshotId={snapshotId}
              language={language}
              execution={execution.data.profile}
              onBusyChange={() => undefined}
            />
          )}
          <Card>
            <CardHeader>
              <CardTitle role="heading" aria-level={2}>
                {t.versions}
              </CardTitle>
            </CardHeader>
            <CardContent>
              {reports.data?.length === 0 && (
                <p className="text-sm text-muted-foreground">{t.noVersions}</p>
              )}
              <ul className="flex flex-col divide-y text-sm">
                {reports.data?.toReversed().map((report) => (
                  <li key={report.id} className="flex items-center justify-between gap-3 py-2">
                    <Link
                      to="/cv-checks/$snapshotId/reports/$reportId"
                      params={{ snapshotId, reportId: report.id }}
                      className="text-brand-text underline"
                    >
                      {t.version(report.version, shortDate(report.created_at, language))}
                    </Link>
                    <span className="text-muted-foreground tabular-nums">
                      {report.overall === null
                        ? t.unscored
                        : `${score(report.overall, language)} / 5`}
                    </span>
                  </li>
                ))}
              </ul>
            </CardContent>
          </Card>
        </div>
      </div>
    </Page>
  )
}
