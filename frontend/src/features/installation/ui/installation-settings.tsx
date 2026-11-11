import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useInstallation } from '../model/use-installation'
import { CheckCircle2, Download, HardDrive, LoaderCircle, Monitor, Volume2 } from 'lucide-react'
import { useState } from 'react'

import { api, isRunning, localizeProblem } from '@/shared/api'
import { usePreferences } from '@/shared/lib/preferences'
import { Button } from '@/shared/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/shared/ui/card'
import { Input } from '@/shared/ui/input'
import { Label } from '@/shared/ui/label'
import { Progress } from '@/shared/ui/progress'

function text(data: FormData, name: string) {
  const value = data.get(name)
  return typeof value === 'string' ? value : ''
}

const size = (bytes: number) =>
  bytes >= 1_000_000_000
    ? `${(bytes / 1_000_000_000).toFixed(2)} GB`
    : `${Math.ceil(bytes / 1_000_000)} MB`

const TITLES: Record<string, readonly [string, string]> = {
  parakeet: ['Riconoscimento vocale · Parakeet', 'Speech recognition · Parakeet'],
  'piper-it': ['Voce italiana · Serena', 'Italian voice · Serena'],
  laya: ['Limiti dichiarati · Laya', 'Stated limits · Laya'],
  whisper: ['Seconda trascrizione · Whisper', 'Second transcription · Whisper'],
}

export function InstallationSettings() {
  const it = usePreferences().language === 'it'
  const query = useInstallation()
  const client = useQueryClient()
  const [connection, setConnection] = useState<boolean | null>(null)
  const [preview, setPreview] = useState(false)
  const [previewError, setPreviewError] = useState(false)
  const install = useMutation({
    mutationFn: async (identity: string) =>
      identity === 'base' ? api.installBase() : [await api.installModel(identity)],
    onSuccess: () => {
      void client.invalidateQueries()
    },
  })
  const configure = useMutation({
    mutationFn: api.configureInstallation,
    onSuccess: () => {
      void client.invalidateQueries()
    },
  })
  const pull = useMutation({
    mutationFn: api.pullLocalModel,
    onSuccess: () => {
      void client.invalidateQueries()
    },
  })
  const connectionCheck = useMutation({
    mutationFn: api.ollamaStatus,
    onSuccess: (value) => {
      setConnection(value.available)
    },
  })
  const state = query.data
  if (!state)
    return (
      <p role="status">
        {query.isError
          ? query.error.message
          : it
            ? 'Verifica dell’installazione…'
            : 'Checking installation…'}
      </p>
    )
  if (!state.managed) return null
  const locked = state.locked || install.isPending || configure.isPending || pull.isPending
  const config = state.config
  const provisioning = state.provisioning
  const error = install.error ?? configure.error ?? pull.error ?? connectionCheck.error
  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Download className="size-5 text-brand-text" />
          {it ? 'Installazione e modelli' : 'Installation and models'}
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-6">
        <p className="text-sm text-muted-foreground">
          {it
            ? 'Voce e riconoscimento funzionano su questa macchina. Installa soltanto ciò che vuoi usare; i modelli linguistici locali sono facoltativi.'
            : 'Speech runs on this machine. Install only what you use; local language models are optional.'}
        </p>
        {provisioning.available ? (
          <div className="grid gap-3 rounded-xl border bg-muted/30 p-4 text-sm sm:grid-cols-2">
            <p className="flex items-center gap-2">
              <HardDrive className="size-4" />
              {it ? 'Spazio disponibile' : 'Available space'}: {size(provisioning.free_bytes ?? 0)}
            </p>
            <p className="flex items-center gap-2">
              <Monitor className="size-4" />
              {provisioning.architecture} · {provisioning.cpus} CPU ·{' '}
              {size(provisioning.memory_bytes ?? 0)} RAM
            </p>
            <p className="text-xs text-muted-foreground sm:col-span-2">
              {it
                ? 'Risorse disponibili a Docker Desktop. Puoi aumentarle nelle sue impostazioni.'
                : 'Resources available to Docker Desktop. You can increase them in its settings.'}
            </p>
          </div>
        ) : (
          <p role="alert">
            {it
              ? 'Il servizio di installazione non è raggiungibile. Riavvia ProbeLoop con il launcher e riprova.'
              : 'The installer service is unavailable. Start ProbeLoop with the launcher and try again.'}
          </p>
        )}
        <div className="flex flex-wrap items-center gap-3">
          <Button
            disabled={locked || !provisioning.available}
            onClick={() => {
              install.mutate('base')
            }}
          >
            {install.isPending ? (
              <LoaderCircle className="size-4 animate-spin" />
            ) : (
              <Download className="size-4" />
            )}
            {it ? 'Installa i componenti vocali e Laya' : 'Install speech components and Laya'}
          </Button>
          <Button
            variant="outline"
            disabled={locked}
            onClick={() => {
              setPreviewError(false)
              setPreview(true)
            }}
          >
            <Volume2 className="size-4" />
            {it ? 'Prova la voce' : 'Test voice'}
          </Button>
        </div>
        {preview && (
          <audio
            controls
            autoPlay
            src="/api/installation/voice-preview"
            className="w-full"
            onError={() => {
              setPreview(false)
              setPreviewError(true)
            }}
          />
        )}
        {previewError && (
          <p role="status" className="text-sm text-muted-foreground">
            {it
              ? 'La voce non è pronta. Installa il componente vocale, attendi il caricamento e riprova.'
              : 'Speech is not ready. Install the voice, wait for loading and try again.'}
          </p>
        )}
        <div className="divide-y rounded-xl border">
          {provisioning.models.map((model) => (
            <div key={model.id} className="flex flex-wrap items-center justify-between gap-3 p-4">
              <div className="min-w-0 space-y-1">
                <p className="flex items-center gap-2 font-medium">
                  {model.state === 'ready' && <CheckCircle2 className="size-4 text-success" />}
                  {TITLES[model.id]?.[it ? 0 : 1] ?? model.title}
                </p>
                <p className="text-xs text-muted-foreground">
                  {size(model.bytes)} ·{' '}
                  <a
                    href={model.source}
                    target="_blank"
                    rel="noreferrer"
                    className="underline underline-offset-4"
                  >
                    {model.license}
                  </a>{' '}
                  ·{' '}
                  {model.state === 'ready'
                    ? it
                      ? 'Verificato'
                      : 'Verified'
                    : model.state === 'unverified'
                      ? it
                        ? 'Da verificare'
                        : 'Verification needed'
                      : model.state === 'partial'
                        ? it
                          ? 'Installazione parziale'
                          : 'Partial installation'
                        : it
                          ? 'Da installare'
                          : 'Not installed'}
                </p>
                {model.id === 'laya' && !model.download_available && !config.limits_url && (
                  <p className="text-xs text-muted-foreground">
                    {it
                      ? 'Indica sotto l’indirizzo della versione pubblicata.'
                      : 'Enter the published version URL below.'}
                  </p>
                )}
              </div>
              <Button
                variant="outline"
                size="sm"
                disabled={
                  locked ||
                  (model.id === 'whisper' && !config.refinement) ||
                  (!model.download_available && !config.limits_url && model.state === 'missing')
                }
                onClick={() => {
                  install.mutate(model.id)
                }}
              >
                {model.id === 'whisper' && !config.refinement
                  ? it
                    ? 'Facoltativo'
                    : 'Optional'
                  : model.state === 'ready'
                    ? it
                      ? 'Ricontrolla'
                      : 'Check again'
                    : model.state === 'unverified'
                      ? it
                        ? 'Verifica'
                        : 'Verify'
                      : it
                        ? 'Installa'
                        : 'Install'}
              </Button>
            </div>
          ))}
        </div>
        {(state.jobs ?? []).map((job) => (
          <div key={job.id} className="space-y-2 text-sm" role="status">
            <p>
              {TITLES[job.subject_id]?.[it ? 0 : 1] ??
                state.local_models[job.subject_id] ??
                job.subject_id}{' '}
              ·{' '}
              {job.status === 'succeeded'
                ? it
                  ? 'Completato'
                  : 'Complete'
                : job.status === 'failed'
                  ? it
                    ? 'Non completato'
                    : 'Failed'
                  : job.status === 'queued'
                    ? it
                      ? 'In attesa'
                      : 'Queued'
                    : it
                      ? 'Installazione in corso…'
                      : 'Installing…'}
            </p>
            {isRunning(job) && (
              <Progress
                value={job.progress * 100}
                aria-label={it ? 'Download del modello' : 'Model download'}
              />
            )}
            {job.error && (
              <p role="alert" className="text-destructive">
                {localizeProblem(job.error, it ? 'it' : 'en')}
              </p>
            )}
          </div>
        ))}
        <form
          key={JSON.stringify(config)}
          className="space-y-5"
          onSubmit={(event) => {
            event.preventDefault()
            const data = new FormData(event.currentTarget)
            configure.mutate({
              refinement: data.get('refinement') === 'on',
              ollama_url: text(data, 'ollama_url'),
              limits_url: text(data, 'limits_url'),
            })
          }}
        >
          <div className="rounded-xl border p-4">
            <label className="flex items-start gap-3 text-sm">
              <input
                name="refinement"
                type="checkbox"
                defaultChecked={config.refinement}
                disabled={locked}
                className="mt-1 accent-brand"
              />
              <span>
                <span className="font-medium">
                  {it ? 'Seconda trascrizione con Whisper' : 'Second transcription with Whisper'}
                </span>
                <span className="mt-1 block text-muted-foreground">
                  {it
                    ? 'Facoltativa. Se la attivi, scarichiamo Whisper e riascoltiamo le risposte dopo il colloquio. Puoi sempre ascoltare e correggere il testo a mano.'
                    : 'Optional. Enabling it downloads Whisper and transcribes answers again after the interview. Listening and manual edits always remain available.'}
                </span>
              </span>
            </label>
          </div>
          <details className="rounded-xl border p-4">
            <summary className="cursor-pointer text-sm font-medium">
              {it ? 'Ollama e indirizzo del modello Laya' : 'Ollama and Laya model address'}
            </summary>
            <div className="mt-5 space-y-5">
              <div className="space-y-2">
                <Label htmlFor="ollama-url">{it ? 'Indirizzo di Ollama' : 'Ollama address'}</Label>
                <Input
                  id="ollama-url"
                  type="url"
                  name="ollama_url"
                  defaultValue={config.ollama_url}
                  disabled={locked}
                  required
                />
                <p className="text-xs text-muted-foreground">
                  {it
                    ? 'Facoltativo per l’uso con ChatGPT. Installa Ollama sull’host, avvialo e verifica la connessione.'
                    : 'Optional when using ChatGPT. Install Ollama on the host, start it and check the connection.'}{' '}
                  <a
                    href="https://ollama.com/download"
                    target="_blank"
                    rel="noreferrer"
                    className="underline"
                  >
                    {it ? 'Scarica Ollama' : 'Download Ollama'}
                  </a>
                </p>
              </div>
              <p className="text-xs text-muted-foreground">
                {it
                  ? 'Salva l’indirizzo prima di verificarlo. Per un server su questa macchina usa host.docker.internal:11434. Se non è raggiungibile, consulta la guida specifica per il tuo sistema.'
                  : 'Save the address before testing it. For this machine use host.docker.internal:11434. If unreachable, follow the guide for your system.'}{' '}
                <a
                  href="https://docs.ollama.com/faq#how-do-i-configure-ollama-server"
                  target="_blank"
                  rel="noreferrer"
                  className="underline"
                >
                  Windows · macOS · Linux
                </a>
              </p>
              <Button
                type="button"
                variant="outline"
                disabled={locked || connectionCheck.isPending}
                onClick={() => {
                  connectionCheck.mutate()
                }}
              >
                {it ? 'Verifica Ollama' : 'Check Ollama'}
              </Button>
              {connection !== null && (
                <p role="status" className="text-sm">
                  {connection
                    ? it
                      ? 'Ollama è raggiungibile.'
                      : 'Ollama is reachable.'
                    : it
                      ? 'Ollama non è raggiungibile. Controlla indirizzo, configurazione e avvio del servizio.'
                      : 'Ollama is unreachable. Check its address, configuration and running status.'}
                </p>
              )}
              <div className="flex flex-wrap gap-2">
                {Object.entries(state.local_models)
                  .filter(([role]) => role !== 'limits')
                  .filter(
                    ([, model], index, entries) =>
                      entries.findIndex(([, other]) => other === model) === index,
                  )
                  .map(([role, model]) => (
                    <Button
                      type="button"
                      variant="outline"
                      size="sm"
                      key={role}
                      disabled={locked || connection !== true}
                      onClick={() => {
                        pull.mutate(role)
                      }}
                    >
                      {it ? 'Installa' : 'Install'} {model}
                    </Button>
                  ))}
              </div>
              <div className="space-y-2">
                <Label htmlFor="limits-url">
                  {it ? 'Indirizzo della versione Laya' : 'Laya version URL'}
                </Label>
                <Input
                  id="limits-url"
                  type="url"
                  name="limits_url"
                  defaultValue={config.limits_url}
                  disabled={locked}
                  placeholder="https://huggingface.co/…/resolve/…"
                />
                <p className="text-xs text-muted-foreground">
                  {it
                    ? 'Viene accettato solo il modello previsto da questa versione dell’app, verificato con le sue checksum.'
                    : 'Only the model approved for this app version is accepted, with checksum verification.'}
                </p>
              </div>
            </div>
          </details>
          <Button type="submit" variant="outline" disabled={locked}>
            {it ? 'Salva configurazione' : 'Save configuration'}
          </Button>
        </form>
        {locked && (
          <p role="status" className="text-sm text-muted-foreground">
            {it
              ? 'Attendi il completamento delle operazioni e chiudi i colloqui attivi prima di modificare l’installazione.'
              : 'Wait for background work and close active interviews before changing the installation.'}
          </p>
        )}
        {error && (
          <p role="alert" className="text-sm text-destructive">
            {error.message}
          </p>
        )}
      </CardContent>
    </Card>
  )
}
