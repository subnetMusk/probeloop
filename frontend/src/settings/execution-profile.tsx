import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'

import { api, type ExecutionProfile, type ExecutionView } from '@/api/rest'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { useLanguage } from '@/settings/preferences'

const QUERY_KEY = ['execution-profile']
const USAGE_URL = 'https://chatgpt.com/settings/usage'

type Models = ExecutionView['profiles'][number]['models']

const ROLES: readonly (readonly [keyof Models, string, string])[] = [
  ['interviewer', 'Intervistatore', 'Interviewer'],
  ['analysis', 'Analisi dei documenti', 'Document analysis'],
  ['evaluation', 'Valutazioni e report', 'Evaluations and reports'],
]

// Outcomes of the sign-in callback (`/settings?chatgpt=...`), in both languages.
const OUTCOMES: Record<string, [string, string]> = {
  connected: [
    'Accesso con ChatGPT riuscito. Scegli il profilo «Piano ChatGPT» per usarlo: l’utilizzo idoneo conterà sul tuo piano ChatGPT.',
    'Signed in with ChatGPT. Choose the "ChatGPT plan" profile to use it: eligible usage then counts against your ChatGPT plan.',
  ],
  'no-plan': [
    'Accesso riuscito, ma ProbeLoop non è stato autorizzato a usare il tuo piano ChatGPT.',
    'Signed in, but ProbeLoop was not allowed to use your ChatGPT plan.',
  ],
  denied: ['Accesso con ChatGPT annullato.', 'Sign-in with ChatGPT was cancelled.'],
  expired: [
    'L’accesso è scaduto o è stato avviato altrove; riprova.',
    'The sign-in expired or was started elsewhere; try again.',
  ],
  failed: [
    'Accesso con ChatGPT non riuscito. L’uso del piano potrebbe non essere ancora disponibile per questa app.',
    'Sign-in with ChatGPT failed. Plan usage may not be available for this app yet.',
  ],
}

function ManageUsage({ it }: { it: boolean }) {
  return (
    <a href={USAGE_URL} target="_blank" rel="noreferrer" className="text-sm underline">
      {it ? 'Gestisci utilizzo' : 'Manage usage'}
    </a>
  )
}

/** Where the interviewer, document analysis and evaluation models run (server setting). */
export function ExecutionProfileSettings() {
  const it = useLanguage() === 'it'
  const client = useQueryClient()
  const [outcome, setOutcome] = useState(() =>
    new URLSearchParams(window.location.search).get('chatgpt'),
  )
  const execution = useQuery({ queryKey: QUERY_KEY, queryFn: api.executionProfile })
  const update = (view: ExecutionView) => {
    client.setQueryData(QUERY_KEY, view)
  }
  const select = useMutation({ mutationFn: api.selectExecutionProfile, onSuccess: update })
  const signOut = useMutation({ mutationFn: api.chatGptSignOut, onSuccess: update })
  const signIn = useMutation({
    mutationFn: api.chatGptSignIn,
    onSuccess: ({ url }) => {
      window.location.assign(url)
    },
  })
  const choose = (profile: ExecutionProfile) => {
    if (profile === execution.data?.profile) return
    if (profile === 'cloud') {
      const confirmed = window.confirm(
        it
          ? 'Con il piano ChatGPT, CV, documenti, trascritti e risposte vengono inviati a OpenAI per l’intervistatore, l’analisi dei documenti e i report, e l’utilizzo conta sul tuo piano ChatGPT. Riconoscimento e sintesi vocale restano su questo computer. Continuare?'
          : 'With the ChatGPT plan, CVs, documents, transcripts and answers are sent to OpenAI for the interviewer, document analysis and reports, and usage counts against your ChatGPT plan. Speech recognition and synthesis stay on this computer. Continue?',
      )
      if (!confirmed) return
    }
    select.mutate(profile)
  }
  const view = execution.data
  const account = view?.chatgpt
  const busy = select.isPending || signIn.isPending || signOut.isPending
  const error = execution.error ?? select.error ?? signIn.error ?? signOut.error
  const outcomeText = outcome ? OUTCOMES[outcome] : undefined
  const continueButton = (
    <Button
      className="self-start"
      disabled={busy}
      onClick={() => {
        signIn.mutate()
      }}
    >
      {it ? 'Continua con ChatGPT' : 'Continue with ChatGPT'}
    </Button>
  )
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
        {outcomeText && (
          <div role="status" className="flex flex-col gap-2 rounded-lg border p-3 text-sm">
            <p>{it ? outcomeText[0] : outcomeText[1]}</p>
            <Button
              variant="outline"
              size="sm"
              className="self-start"
              onClick={() => {
                setOutcome(null)
                window.history.replaceState(null, '', window.location.pathname)
              }}
            >
              {it ? 'Ho capito' : 'Got it'}
            </Button>
          </div>
        )}
        {view && account && (
          <fieldset className="flex flex-col gap-3" disabled={busy}>
            <legend className="sr-only">
              {it ? 'Profilo di esecuzione' : 'Execution profile'}
            </legend>
            {view.profiles.map((profile) => {
              const cloud = profile.id === 'cloud'
              const available = !cloud || account.plan_usage
              const checked = view.profile === profile.id
              return (
                <label
                  key={profile.id}
                  className={`flex gap-3 rounded-lg border p-3 ${
                    available ? 'cursor-pointer' : ''
                  } ${checked ? 'border-indigo-600' : ''}`}
                >
                  <input
                    type="radio"
                    name="execution-profile"
                    value={profile.id}
                    checked={checked}
                    disabled={!available}
                    onChange={() => {
                      choose(profile.id)
                    }}
                    className="mt-1 accent-indigo-600"
                  />
                  <span className="flex flex-col gap-1">
                    <span className="font-medium">
                      {cloud ? (it ? 'Piano ChatGPT' : 'ChatGPT plan') : it ? 'Locale' : 'Local'}
                    </span>
                    <span className="text-sm text-muted-foreground">
                      {cloud
                        ? it
                          ? 'Intervistatore, analisi dei documenti e valutazioni usano i modelli di ChatGPT con il tuo piano (Plus o Pro), non le API a consumo.'
                          : 'The interviewer, document analysis and evaluations use ChatGPT models through your plan (Plus or Pro), not pay-per-use API billing.'
                        : it
                          ? 'Tutti i modelli girano su questo computer con Ollama. Nessun dato lascia la macchina.'
                          : 'Every model runs on this computer through Ollama. No data leaves the machine.'}
                    </span>
                    <span className="text-sm text-muted-foreground">
                      {ROLES.map(([role, roleIt, roleEn]) => (
                        <span key={role} className="block">
                          {it ? roleIt : roleEn}: <code>{profile.models[role]}</code>
                        </span>
                      ))}
                    </span>
                  </span>
                </label>
              )
            })}
          </fieldset>
        )}
        {account && (
          <section
            aria-label={it ? 'Account ChatGPT' : 'ChatGPT account'}
            className="flex flex-col gap-2 rounded-lg border p-3 text-sm"
          >
            {account.signed_in ? (
              <>
                <p>
                  {it ? 'Accesso effettuato come' : 'Signed in as'}{' '}
                  <strong>{account.email ?? (it ? 'account ChatGPT' : 'ChatGPT account')}</strong>
                  {account.plan_usage
                    ? ''
                    : it
                      ? ', ma ProbeLoop non può usare il tuo piano: accedi di nuovo per consentirlo.'
                      : ', but ProbeLoop may not use your plan: sign in again to allow it.'}
                </p>
                <div className="flex flex-wrap items-center gap-3">
                  {!account.plan_usage && continueButton}
                  <Button
                    variant="outline"
                    size="sm"
                    disabled={busy}
                    onClick={() => {
                      signOut.mutate()
                    }}
                  >
                    {it ? 'Esci da ChatGPT' : 'Sign out of ChatGPT'}
                  </Button>
                  <ManageUsage it={it} />
                </div>
              </>
            ) : (
              <>
                <p className="font-medium">
                  {it ? 'Usa il tuo piano ChatGPT' : 'Use your ChatGPT plan'}
                </p>
                <p className="text-muted-foreground">
                  {it
                    ? 'Completa le richieste AI idonee di questa app con l’utilizzo incluso nel tuo piano ChatGPT o nel saldo crediti.'
                    : 'Complete eligible AI requests in this app with usage included in your ChatGPT plan or credits balance.'}
                </p>
                {continueButton}
              </>
            )}
          </section>
        )}
        {view?.profile === 'cloud' && (
          <p role="note" className="rounded-lg border border-amber-500/60 p-3 text-sm">
            {it ? 'Piano ChatGPT in uso' : 'Using ChatGPT plan'}:{' '}
            {it
              ? 'CV, documenti, trascritti e risposte vengono inviati a OpenAI. I report generati con modelli diversi non si confrontano nei progressi. '
              : 'CVs, documents, transcripts and answers are sent to OpenAI. Reports from different models are not compared in progress views. '}
            <ManageUsage it={it} />
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
