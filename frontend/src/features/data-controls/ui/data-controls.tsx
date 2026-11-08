import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { api } from '@/shared/api'
import { Button } from '@/shared/ui/button'
import { Card, CardHeader, CardTitle, CardContent, CardDescription } from '@/shared/ui/card'
import { PREPARATION_KEY } from '@/entities/preparation'
import { clearReportJobs } from '@/entities/report-job'
import { resetPreferences, useLanguage } from '@/shared/lib/preferences'

export function DataControls() {
  const it = useLanguage() === 'it'
  const client = useQueryClient()
  const summary = useQuery({ queryKey: ['data-summary'], queryFn: api.dataSummary })
  const jobs = useQuery({
    queryKey: ['pending-jobs'],
    queryFn: api.pendingJobs,
    refetchInterval: 3000,
  })
  const backup = useMutation({
    mutationFn: api.prepareBackup,
    onSuccess: ({ id }) => {
      window.location.assign(`/api/data/backup/${id}`)
    },
  })
  const remove = useMutation({
    mutationFn: api.deleteAllData,
    onSuccess: () => {
      client.clear()
      resetPreferences()
      clearReportJobs()
      try {
        sessionStorage.removeItem(PREPARATION_KEY)
      } catch {
        /* The page reload clears transient state. */
      }
      window.location.replace('/settings?deleted=1')
    },
  })
  const exporting = useMutation({
    mutationFn: async () => {
      const response = await fetch('/api/data/export')
      if (!response.ok) {
        const body = (await response.json()) as { detail?: string }
        throw new Error(body.detail ?? response.statusText)
      }
      const url = URL.createObjectURL(await response.blob())
      const link = document.createElement('a')
      link.href = url
      link.download = 'probeloop-data.json'
      link.click()
      window.setTimeout(() => {
        URL.revokeObjectURL(url)
      }, 1000)
    },
  })
  const unavailable =
    !summary.isSuccess ||
    jobs.data === undefined ||
    jobs.data.length > 0 ||
    backup.isPending ||
    remove.isPending ||
    exporting.isPending
  const error = summary.error ?? backup.error ?? remove.error ?? exporting.error
  return (
    <Card>
      <CardHeader>
        <CardTitle>{it ? 'I tuoi dati' : 'Your data'}</CardTitle>
        <CardDescription>
          {it
            ? 'Esporta i dati strutturati o crea un backup con documenti, registrazioni e report. Attendi la fine delle elaborazioni e chiudi eventuali colloqui aperti.'
            : 'Export structured data or create a backup including documents, recordings and reports. Wait for processing and close open interviews first.'}
        </CardDescription>
      </CardHeader>
      <CardContent className="flex flex-col gap-4">
        <p>
          {summary.data?.interview_sessions ?? 0} {it ? 'colloqui' : 'interviews'} ·{' '}
          {summary.data?.documents ?? 0} {it ? 'documenti' : 'documents'} ·{' '}
          {summary.data?.reports ?? 0} {it ? 'versioni di report' : 'report versions'}
        </p>
        <div className="flex flex-wrap gap-2">
          <Button
            variant="outline"
            disabled={unavailable}
            onClick={() => {
              exporting.mutate()
            }}
          >
            JSON
          </Button>
          <Button
            variant="outline"
            disabled={unavailable}
            onClick={() => {
              backup.mutate()
            }}
          >
            {backup.isPending
              ? it
                ? 'Preparazione backup…'
                : 'Preparing backup…'
              : it
                ? 'Scarica backup ZIP'
                : 'Download ZIP backup'}
          </Button>
        </div>
        <p className="text-sm text-muted-foreground">
          {it
            ? 'Modelli e configurazione del server non sono inclusi. Il backup può contenere dati personali: conserva il file dove preferisci.'
            : 'Models and server configuration are excluded. The backup can contain personal data; choose where to keep it.'}
        </p>
        <Button
          variant="destructive"
          className="self-start"
          disabled={unavailable}
          onClick={() => {
            const confirmed = window.confirm(
              it
                ? `Eliminare definitivamente tutti i dati di ProbeLoop? ${summary.data?.interview_sessions ?? 0} colloqui e tutti i documenti, profili, trascritti, registrazioni e report verranno rimossi. Anche le preferenze del browser verranno azzerate.`
                : `Permanently delete all ProbeLoop data? ${summary.data?.interview_sessions ?? 0} interviews and all documents, profiles, transcripts, recordings and reports will be removed. Browser preferences will also be reset.`,
            )
            if (confirmed) remove.mutate()
          }}
        >
          {it ? 'Elimina tutti i miei dati' : 'Delete all my data'}
        </Button>
        {new URLSearchParams(window.location.search).get('deleted') === '1' && (
          <p role="status">
            {it ? 'I dati dell’app sono stati eliminati.' : 'Application data deleted.'}
          </p>
        )}
        {error && (
          <p role="alert" className="text-destructive">
            {error.message}
          </p>
        )}
      </CardContent>
    </Card>
  )
}
