import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Link } from '@tanstack/react-router'
import {
  CheckIcon,
  CloudIcon,
  CpuIcon,
  RefreshCwIcon,
  Settings2Icon,
  SparklesIcon,
} from 'lucide-react'
import { useState } from 'react'

import { api, type ExecutionView } from '@/shared/api'
import { useLanguage } from '@/shared/lib/preferences'
import { Badge } from '@/shared/ui/badge'
import { Button } from '@/shared/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/shared/ui/card'
import { Label } from '@/shared/ui/label'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/shared/ui/select'

type ToolRole = ExecutionView['tools'][number]
type Tool = ToolRole['selected']
const QUERY_KEY = ['execution-profile']
const USAGE_URL = 'https://chatgpt.com/settings/usage'
const LABELS = {
  interviewer: ['Intervistatore', 'Interviewer'],
  analysis: ['Analisi dei documenti', 'Document analysis'],
  evaluation: ['Valutazioni e report', 'Evaluations and reports'],
  limits: ['Limiti dichiarati', 'Stated limits'],
} as const
const DESCRIPTIONS = {
  interviewer: [
    'Conduce il colloquio e formula le domande.',
    'Conducts the interview and writes its questions.',
  ],
  analysis: [
    'Legge CV, offerte e risorse per preparare il colloquio.',
    'Reads CVs, job offers and resources to prepare the interview.',
  ],
  evaluation: [
    'Analizza le risposte e genera i report e i CV check.',
    'Assesses answers and produces reports and CV checks.',
  ],
  limits: [
    'Riconosce ciò che dichiari di non ricordare o non aver mai fatto.',
    'Recognises what you say you cannot recall or have never done.',
  ],
} as const

const toolName = (tool: Tool, it: boolean) =>
  ({ local: it ? 'LLM locale' : 'Local LLM', cloud: 'ChatGPT', laya: 'Laya', jev: 'Jev' })[tool]

function ToolIcon({ tool }: { tool: Tool }) {
  const Icon = tool === 'local' ? CpuIcon : tool === 'cloud' ? CloudIcon : SparklesIcon
  return <Icon className="size-4 shrink-0" aria-hidden="true" />
}

function reasonText(reason: string, it: boolean) {
  const messages: Record<string, [string, string]> = {
    ready: ['Disponibile', 'Available'],
    model_missing: ['Modello non disponibile', 'Model unavailable'],
    sign_in_required: ['Accedi con ChatGPT', 'Sign in with ChatGPT'],
    loading: ['Caricamento del modello', 'Loading model'],
    model_invalid: ['Modello da reinstallare', 'Reinstall model'],
    two_step_required: ['Richiede il colloquio in due passi', 'Requires two-step interviews'],
  }
  return messages[reason]?.[it ? 0 : 1] ?? (it ? 'Non disponibile' : 'Unavailable')
}

function useExecution() {
  return useQuery({
    queryKey: QUERY_KEY,
    queryFn: api.executionProfile,
    refetchInterval: (query) =>
      query.state.data?.tools.some((role) => role.options.some((o) => o.reason === 'loading'))
        ? 3000
        : 30000,
  })
}

/** A read-only summary of the defaults used for new work. Changes live in Settings. */
export function ActiveToolsSummary() {
  const it = useLanguage() === 'it'
  const execution = useExecution()
  return (
    <section
      aria-labelledby="active-tools-title"
      className="overflow-hidden rounded-xl border bg-card"
    >
      <div className="flex flex-wrap items-center justify-between gap-3 border-b bg-muted/30 px-5 py-3">
        <h2 id="active-tools-title" className="flex items-center gap-2 text-sm font-semibold">
          <Settings2Icon className="size-4 text-brand-text" aria-hidden="true" />
          {it ? 'Strumenti in uso' : 'Active tools'}
        </h2>
        <Link
          to="/settings"
          className="text-sm font-medium text-brand-text underline-offset-4 hover:underline"
        >
          {it ? 'Modifica nelle Impostazioni' : 'Change in Settings'}
        </Link>
      </div>
      <div className="grid gap-5 px-5 py-4 sm:grid-cols-2 xl:grid-cols-4">
        {execution.data?.tools.map((role) => {
          const option = role.options.find((o) => o.id === role.selected)
          return (
            <div key={role.id} className="min-w-0">
              <p className="text-xs text-muted-foreground">{LABELS[role.id][it ? 0 : 1]}</p>
              <p className="mt-1.5 flex items-center gap-2 text-sm font-medium">
                <ToolIcon tool={role.selected} />
                {toolName(role.selected, it)}
              </p>
              {!option?.available && (
                <p className="mt-1 text-xs text-destructive">
                  {reasonText(option?.reason ?? '', it)}
                </p>
              )}
            </div>
          )
        })}
        {execution.isPending && (
          <p className="text-sm text-muted-foreground">
            {it ? 'Verifica degli strumenti…' : 'Checking tools…'}
          </p>
        )}
        {execution.error && (
          <p role="alert" className="text-sm text-destructive">
            {execution.error.message}
          </p>
        )}
      </div>
    </section>
  )
}

/** Per-role tool selection. Availability is checked and enforced by the server. */
export function ExecutionProfileSettings() {
  const it = useLanguage() === 'it'
  const client = useQueryClient()
  const execution = useExecution()
  const [outcome, setOutcome] = useState(() =>
    new URLSearchParams(window.location.search).get('chatgpt'),
  )
  const update = (view: ExecutionView) => client.setQueryData(QUERY_KEY, view)
  const select = useMutation({ mutationFn: api.selectExecutionTools, onSuccess: update })
  const signOut = useMutation({ mutationFn: api.chatGptSignOut, onSuccess: update })
  const signIn = useMutation({
    mutationFn: api.chatGptSignIn,
    onSuccess: ({ url }) => {
      window.location.assign(url)
    },
  })
  const account = execution.data?.chatgpt
  const busy = select.isPending || signIn.isPending || signOut.isPending
  const error = execution.error ?? select.error ?? signIn.error ?? signOut.error
  const cloud = execution.data?.tools.some((role) => role.selected === 'cloud')
  const outcomes: Record<string, [string, string]> = {
    connected: [
      'Accesso con ChatGPT riuscito. Ora puoi selezionarlo per gli ambiti che preferisci.',
      'Signed in with ChatGPT. You can now select it for the roles you prefer.',
    ],
    'no-plan': [
      'Accesso riuscito, ma l’utilizzo del piano non è autorizzato. Accedi di nuovo.',
      'Signed in, but plan usage is not authorised. Sign in again.',
    ],
    denied: ['Accesso con ChatGPT annullato.', 'ChatGPT sign-in cancelled.'],
    expired: ['Accesso scaduto. Riprova.', 'Sign-in expired. Try again.'],
    failed: ['Accesso con ChatGPT non riuscito. Riprova.', 'ChatGPT sign-in failed. Try again.'],
  }
  return (
    <Card className="overflow-hidden border-brand/25">
      <CardHeader className="border-b bg-muted/20">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <CardTitle className="flex items-center gap-2">
            <Settings2Icon className="size-5 text-brand-text" aria-hidden="true" />
            {it ? 'Strumenti di elaborazione' : 'Processing tools'}
          </CardTitle>
          <Button
            variant="ghost"
            size="sm"
            disabled={execution.isFetching}
            onClick={() => void execution.refetch()}
          >
            <RefreshCwIcon
              className={execution.isFetching ? 'animate-spin' : ''}
              aria-hidden="true"
            />
            {it ? 'Verifica disponibilità' : 'Check availability'}
          </Button>
        </div>
        <CardDescription>
          {it
            ? 'Scegli uno strumento per ogni ambito. Le modifiche si salvano subito e valgono per i nuovi lavori; quelli già preparati mantengono le loro scelte.'
            : 'Choose a tool for each role. Changes save immediately and apply to new work; existing preparations keep their choices.'}
        </CardDescription>
      </CardHeader>
      <CardContent className="flex flex-col gap-6 pt-6">
        {outcome && outcomes[outcome] && (
          <div
            role="status"
            className="flex flex-wrap items-center justify-between gap-3 rounded-lg border bg-muted/30 p-3 text-sm"
          >
            <p>{outcomes[outcome][it ? 0 : 1]}</p>
            <Button
              variant="ghost"
              size="sm"
              onClick={() => {
                setOutcome(null)
                window.history.replaceState(null, '', window.location.pathname)
              }}
            >
              {it ? 'Ho capito' : 'Got it'}
            </Button>
          </div>
        )}
        <div className="divide-y">
          {execution.data?.tools.map((role) => {
            const option = role.options.find((o) => o.id === role.selected)
            const id = `tool-${role.id}`
            return (
              <div
                key={role.id}
                className="grid gap-4 py-5 first:pt-0 last:pb-0 sm:grid-cols-[1fr_15rem] sm:items-start"
              >
                <div>
                  <Label htmlFor={id} className="text-base font-semibold">
                    {LABELS[role.id][it ? 0 : 1]}
                  </Label>
                  <p
                    id={`${id}-description`}
                    className="mt-1 max-w-md text-sm text-muted-foreground"
                  >
                    {DESCRIPTIONS[role.id][it ? 0 : 1]}
                  </p>
                  {role.id === 'limits' && role.selected === 'laya' && (
                    <p className="mt-2 text-xs text-muted-foreground">
                      {it
                        ? 'Se lo strumento non è disponibile, il colloquio si ferma fino al ripristino.'
                        : 'If the tool becomes unavailable, the interview stops until it is restored.'}
                    </p>
                  )}
                </div>
                <div className="flex min-w-0 flex-col gap-2">
                  <Select
                    value={role.selected}
                    disabled={busy || execution.data.locked}
                    onValueChange={(value) => {
                      select.mutate({ [role.id]: value as Tool })
                    }}
                  >
                    <SelectTrigger
                      id={id}
                      aria-describedby={`${id}-description`}
                      className="w-full"
                    >
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      {role.options.map((choice) => (
                        <SelectItem key={choice.id} value={choice.id} disabled={!choice.available}>
                          <ToolIcon tool={choice.id} />
                          <span>
                            {toolName(choice.id, it)}
                            {!choice.available && (
                              <span className="text-xs text-muted-foreground">
                                {' '}
                                · {reasonText(choice.reason, it)}
                              </span>
                            )}
                          </span>
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                  <div className="flex items-center gap-1.5 text-xs">
                    {option?.available ? (
                      <>
                        <CheckIcon className="size-3 text-brand-text" aria-hidden="true" />
                        <span>{it ? 'Disponibile' : 'Available'}</span>
                      </>
                    ) : (
                      <span className="text-destructive">
                        {reasonText(option?.reason ?? '', it)}
                      </span>
                    )}
                  </div>
                  {option && role.selected !== 'laya' && (
                    <p className="break-all text-xs text-muted-foreground">
                      {option.model_ref.replace(/^(ollama:|chatgpt:)/, '').replace(/@ctx\d+$/, '')}
                    </p>
                  )}
                </div>
              </div>
            )
          })}
        </div>
        {execution.isPending && (
          <p className="text-sm text-muted-foreground">
            {it ? 'Verifica degli strumenti…' : 'Checking tools…'}
          </p>
        )}
        <section
          aria-label={it ? 'Account ChatGPT' : 'ChatGPT account'}
          className="rounded-xl border bg-muted/20 p-4"
        >
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <h3 className="flex items-center gap-2 text-sm font-semibold">
                <CloudIcon className="size-4" aria-hidden="true" />
                ChatGPT
                {account?.plan_usage && (
                  <Badge variant="outline">{it ? 'Collegato' : 'Connected'}</Badge>
                )}
              </h3>
              <p className="mt-1 text-sm text-muted-foreground">
                {account?.signed_in
                  ? (account.email ?? 'ChatGPT')
                  : it
                    ? 'Collega il tuo account per abilitare ChatGPT nei menu.'
                    : 'Connect your account to enable ChatGPT in the menus.'}
              </p>
            </div>
            <div className="flex flex-wrap items-center gap-3">
              {!account?.plan_usage && (
                <Button
                  disabled={busy}
                  onClick={() => {
                    signIn.mutate()
                  }}
                >
                  {it ? 'Continua con ChatGPT' : 'Continue with ChatGPT'}
                </Button>
              )}
              {account?.signed_in && (
                <Button
                  variant="outline"
                  size="sm"
                  disabled={busy || execution.data?.locked}
                  onClick={() => {
                    signOut.mutate()
                  }}
                >
                  {it ? 'Esci da ChatGPT' : 'Sign out of ChatGPT'}
                </Button>
              )}
              {account?.signed_in && (
                <a href={USAGE_URL} target="_blank" rel="noreferrer" className="text-sm underline">
                  {it ? 'Gestisci utilizzo' : 'Manage usage'}
                </a>
              )}
            </div>
          </div>
          {cloud && (
            <p role="note" className="mt-3 border-t pt-3 text-sm text-muted-foreground">
              {it
                ? 'Gli ambiti impostati su ChatGPT inviano a OpenAI i testi necessari e usano il tuo piano. Audio e strumenti locali restano su questo computer.'
                : 'Roles set to ChatGPT send the required text to OpenAI and use your plan. Audio and local tools stay on this computer.'}
            </p>
          )}
        </section>
        <p className="text-xs text-muted-foreground">
          {it
            ? 'Riconoscimento e sintesi vocale restano sempre in locale. Le opzioni non disponibili sono disabilitate.'
            : 'Speech recognition and synthesis always stay local. Unavailable options are disabled.'}
        </p>
        {execution.data?.locked && (
          <p role="status" className="rounded-lg border bg-muted/40 p-3 text-sm">
            {it
              ? 'Le scelte sono bloccate mentre un colloquio è aperto o un’elaborazione è in corso. Chiudi il colloquio e attendi la fine dei lavori per modificarle.'
              : 'Tool choices are locked while an interview is open or processing is in progress. Close the interview and wait for work to finish before changing them.'}
          </p>
        )}
        {select.isSuccess && !busy && (
          <p role="status" className="flex items-center gap-1.5 text-sm text-brand-text">
            <CheckIcon className="size-4" aria-hidden="true" />
            {it ? 'Configurazione salvata' : 'Configuration saved'}
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
