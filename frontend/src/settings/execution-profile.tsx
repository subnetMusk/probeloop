import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { api, type ExecutionProfile, type ExecutionView } from '@/api/rest'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { useLanguage } from '@/settings/preferences'

const QUERY_KEY = ['execution-profile']

type Models = NonNullable<ExecutionView['profiles'][number]['models']>

const ROLES: readonly (readonly [keyof Models, string, string])[] = [
  ['interviewer', 'Intervistatore', 'Interviewer'],
  ['analysis', 'Analisi dei documenti', 'Document analysis'],
  ['evaluation', 'Valutazioni e report', 'Evaluations and reports'],
]

/** Where the interviewer, document analysis and evaluation models run (server setting). */
export function ExecutionProfileSettings() {
  const it = useLanguage() === 'it'
  const client = useQueryClient()
  const execution = useQuery({ queryKey: QUERY_KEY, queryFn: api.executionProfile })
  const select = useMutation({
    mutationFn: api.selectExecutionProfile,
    onSuccess: (view) => {
      client.setQueryData(QUERY_KEY, view)
    },
  })
  const choose = (profile: ExecutionProfile) => {
    if (profile === execution.data?.profile) return
    if (profile === 'cloud') {
      const confirmed = window.confirm(
        it
          ? 'Con il profilo cloud, CV, documenti, trascritti e risposte vengono inviati al fornitore cloud per l’intervistatore, l’analisi dei documenti e i report. Riconoscimento e sintesi vocale restano su questo computer. Continuare?'
          : 'With the cloud profile, CVs, documents, transcripts and answers are sent to the cloud provider for the interviewer, document analysis and reports. Speech recognition and synthesis stay on this computer. Continue?',
      )
      if (!confirmed) return
    }
    select.mutate(profile)
  }
  const labels: Record<ExecutionProfile, [string, string]> = {
    local: [
      it ? 'Locale' : 'Local',
      it
        ? 'Tutti i modelli girano su questo computer con Ollama. Nessun dato lascia la macchina.'
        : 'Every model runs on this computer through Ollama. No data leaves the machine.',
    ],
    cloud: [
      'Cloud',
      it
        ? 'Intervistatore, analisi dei documenti e valutazioni usano il modello in cloud.'
        : 'The interviewer, document analysis and evaluations use the cloud model.',
    ],
  }
  const view = execution.data
  const error = execution.error ?? select.error
  return (
    <Card>
      <CardHeader>
        <CardTitle>{it ? 'Profilo di esecuzione' : 'Execution profile'}</CardTitle>
        <CardDescription>
          {it
            ? 'Riconoscimento vocale (anche la rifinitura dopo il colloquio) e sintesi vocale girano sempre in locale. Il cambio è possibile senza colloqui aperti né elaborazioni in corso.'
            : 'Speech recognition (including the refinement after the interview) and speech synthesis always run locally. The profile can change when no interview is open and no processing is running.'}
        </CardDescription>
      </CardHeader>
      <CardContent className="flex flex-col gap-4">
        {view && (
          <fieldset className="flex flex-col gap-3" disabled={select.isPending}>
            <legend className="sr-only">
              {it ? 'Profilo di esecuzione' : 'Execution profile'}
            </legend>
            {view.profiles.map((profile) => {
              const [title, description] = labels[profile.id]
              const checked = view.profile === profile.id
              return (
                <label
                  key={profile.id}
                  className={`flex gap-3 rounded-lg border p-3 ${
                    profile.available ? 'cursor-pointer' : 'opacity-60'
                  } ${checked ? 'border-indigo-600' : ''}`}
                >
                  <input
                    type="radio"
                    name="execution-profile"
                    value={profile.id}
                    checked={checked}
                    disabled={!profile.available}
                    onChange={() => {
                      choose(profile.id)
                    }}
                    className="mt-1 accent-indigo-600"
                  />
                  <span className="flex flex-col gap-1">
                    <span className="font-medium">{title}</span>
                    <span className="text-sm text-muted-foreground">{description}</span>
                    {profile.models ? (
                      <span className="text-sm text-muted-foreground">
                        {ROLES.map(([role, roleIt, roleEn]) => (
                          <span key={role} className="block">
                            {it ? roleIt : roleEn}: <code>{profile.models?.[role]}</code>
                          </span>
                        ))}
                      </span>
                    ) : (
                      <span className="text-sm text-muted-foreground">
                        {it
                          ? 'Non configurato: imposta PROBELOOP_CLOUD_API_KEY nel file .env e riavvia il backend.'
                          : 'Not configured: set PROBELOOP_CLOUD_API_KEY in the .env file and restart the backend.'}
                      </span>
                    )}
                  </span>
                </label>
              )
            })}
          </fieldset>
        )}
        {view?.profile === 'cloud' && (
          <p role="note" className="rounded-lg border border-amber-500/60 p-3 text-sm">
            {it
              ? 'Profilo cloud attivo: CV, documenti, trascritti e risposte vengono inviati al fornitore cloud. I report generati con modelli diversi non si confrontano nei progressi.'
              : 'Cloud profile active: CVs, documents, transcripts and answers are sent to the cloud provider. Reports from different models are not compared in progress views.'}
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
