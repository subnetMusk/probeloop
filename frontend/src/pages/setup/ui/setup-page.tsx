import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { ArrowRight, CheckCircle2, ShieldCheck } from 'lucide-react'
import { Link } from '@tanstack/react-router'

import { ExecutionProfileSettings } from '@/features/execution-profile'
import { InstallationSettings, useInstallation } from '@/features/installation'
import { api } from '@/shared/api'
import { usePreferences } from '@/shared/lib/preferences'
import { Button } from '@/shared/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/shared/ui/card'
import { Page, PageHeader } from '@/shared/ui/page-header'

export function SetupPage() {
  const it = usePreferences().language === 'it'
  const installation = useInstallation()
  const execution = useQuery({
    queryKey: ['execution-profile'],
    queryFn: api.executionProfile,
    refetchInterval: 3000,
  })
  const speech = useQuery({
    queryKey: ['speech'],
    queryFn: api.speechStatus,
    refetchInterval: 3000,
  })
  const client = useQueryClient()
  const complete = useMutation({
    mutationFn: api.completeInstallation,
    onSuccess: () => {
      void client.invalidateQueries()
    },
  })
  const toolsReady =
    execution.data?.tools.every((role) =>
      role.options.some((option) => option.id === role.selected && option.available),
    ) ?? false
  return (
    <Page narrow>
      <PageHeader
        title={it ? 'Benvenuto in ProbeLoop' : 'Welcome to ProbeLoop'}
        description={
          it
            ? 'Prepariamo gli strumenti per il tuo primo colloquio. Puoi tornare qui dalle impostazioni.'
            : 'Prepare the tools for your first interview. You can return here from Settings.'
        }
      />
      <div className="rounded-2xl border bg-gradient-to-br from-brand/10 via-background to-background p-6">
        <p className="mb-3 flex items-center gap-2 font-heading text-lg font-semibold">
          <ShieldCheck className="size-5 text-brand-text" />
          {it ? 'Scegli cosa resta sulla tua macchina' : 'Choose what stays on your machine'}
        </p>
        <p className="text-sm leading-relaxed text-muted-foreground">
          {it
            ? 'Riconoscimento vocale, voce e Laya lavorano localmente. Con ChatGPT, il testo necessario alle funzioni selezionate viene inviato al servizio cloud. Ollama è facoltativo e non viene installato nel percorso cloud.'
            : 'Speech recognition, synthesis and Laya run locally. With ChatGPT, text needed by the selected features is sent to the cloud service. Ollama is optional and is not installed for cloud use.'}
        </p>
      </div>
      <section aria-labelledby="setup-tools" className="space-y-4">
        <h2 id="setup-tools" className="font-heading text-lg font-semibold">
          <span className="mr-2 text-brand-text">01</span>
          {it ? 'Collega i tuoi strumenti' : 'Connect your tools'}
        </h2>
        <ExecutionProfileSettings />
      </section>
      <section aria-labelledby="setup-models" className="space-y-4">
        <h2 id="setup-models" className="font-heading text-lg font-semibold">
          <span className="mr-2 text-brand-text">02</span>
          {it
            ? 'Verifica le risorse e installa i componenti'
            : 'Check resources and install components'}
        </h2>
        <InstallationSettings />
      </section>
      <Card>
        <CardHeader>
          <CardTitle>
            <span className="mr-2 text-brand-text">03</span>
            {it ? 'Pronto per iniziare' : 'Ready to begin'}
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <p className="flex items-center gap-2 text-sm">
            {toolsReady && <CheckCircle2 className="size-4 text-success" />}
            {toolsReady
              ? it
                ? 'Gli strumenti selezionati sono disponibili.'
                : 'Your selected tools are available.'
              : it
                ? 'Collega ChatGPT oppure installa i modelli locali, poi scegli uno strumento disponibile per ogni ambito.'
                : 'Connect ChatGPT or install local models, then select an available tool for each role.'}
          </p>
          <p className="text-sm text-muted-foreground">
            {it
              ? 'Terminati i download, puoi usare i colloqui testuali anche mentre i modelli vocali si caricano. Prima di un colloquio vocale verifichiamo anche riconoscimento e sintesi.'
              : 'After downloads finish, you can use text interviews while speech models load. Starting a voice interview also checks recognition and synthesis.'}
          </p>
          {speech.isError && (
            <p className="text-sm text-muted-foreground">
              {it ? 'Verifica vocale non disponibile.' : 'Speech check unavailable.'}
            </p>
          )}
          {speech.data && (
            <p className="flex items-center gap-2 text-sm">
              {speech.data.ready && <CheckCircle2 className="size-4 text-success" />}
              {speech.data.ready
                ? it
                  ? 'Anche la voce è pronta.'
                  : 'Speech is also ready.'
                : it
                  ? 'Voce in preparazione: installa i componenti e attendi il caricamento.'
                  : 'Speech is getting ready: install the components and wait for loading.'}
            </p>
          )}
          {installation.data?.config.completed || complete.isSuccess ? (
            <Button asChild>
              <Link to="/dashboard">
                {it ? 'Apri ProbeLoop' : 'Open ProbeLoop'}
                <ArrowRight className="size-4" />
              </Link>
            </Button>
          ) : (
            <Button
              disabled={!toolsReady || installation.data?.locked || complete.isPending}
              onClick={() => {
                complete.mutate()
              }}
            >
              {it ? 'Completa configurazione' : 'Complete setup'}
              <ArrowRight className="size-4" />
            </Button>
          )}
          {complete.error && (
            <p role="alert" className="text-sm text-destructive">
              {complete.error.message}
            </p>
          )}
        </CardContent>
      </Card>
    </Page>
  )
}
