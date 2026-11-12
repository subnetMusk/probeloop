import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Link } from '@tanstack/react-router'
import {
  CheckIcon,
  CloudIcon,
  CpuIcon,
  KeyRoundIcon,
  ListChecksIcon,
  RefreshCwIcon,
  Settings2Icon,
  SparklesIcon,
  ZapIcon,
} from 'lucide-react'
import { useState } from 'react'

import { api, settingsLockMessage, type ExecutionView } from '@/shared/api'
import { useLanguage } from '@/shared/lib/preferences'
import { Badge } from '@/shared/ui/badge'
import { Button } from '@/shared/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/shared/ui/card'
import { Input } from '@/shared/ui/input'
import { Label } from '@/shared/ui/label'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/shared/ui/select'
import { Switch } from '@/shared/ui/switch'

type ToolRole = ExecutionView['tools'][number]
type Tool = ToolRole['selected']
const QUERY_KEY = ['execution-profile']
const USAGE_URL = 'https://chatgpt.com/settings/usage'
const LABELS = {
  interviewer: ['Intervistatore', 'Interviewer'],
  analysis: ['Analisi dei documenti', 'Document analysis'],
  evaluation: ['Valutazioni e report', 'Evaluations and reports'],
  limits: ['Limiti dichiarati', 'Stated limits'],
  classification: ['Classificazione dei documenti', 'Document classification'],
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
  classification: [
    'Decide se un requisito dell’offerta è obbligatorio o preferito.',
    'Decides whether a requirement of the job offer is required or preferred.',
  ],
} as const

const TYPESAFE_CONSOLE_URL = 'https://console.typesafe.ai'

const toolName = (tool: Tool, it: boolean) =>
  ({
    local: it ? 'LLM locale' : 'Local LLM',
    cloud: 'ChatGPT',
    laya: 'Laya',
    jev: 'Jev',
    rules: it ? 'Regole e modello di analisi' : 'Rules and analysis model',
  })[tool]

const ICONS = {
  local: CpuIcon,
  cloud: CloudIcon,
  laya: SparklesIcon,
  jev: ZapIcon,
  rules: ListChecksIcon,
} as const

function ToolIcon({ tool }: { tool: Tool }) {
  const Icon = ICONS[tool]
  return <Icon className="size-4 shrink-0" aria-hidden="true" />
}

/** The model shown under a selection; Laya is identified by its name alone. */
function modelLabel(tool: Tool, modelRef: string) {
  if (tool === 'laya' || tool === 'rules') return null
  if (tool === 'jev') return modelRef.split(':')[1] ?? modelRef
  return modelRef.replace(/^(ollama:|chatgpt:)/, '').replace(/@ctx\d+$/, '')
}

/**
 * The recommended tool of a role: ChatGPT interviews fastest (single-call turns) and Jev reads
 * stated limits without a local model; without a Jev key, Laya does it on this computer.
 */
function recommended(role: string, jevKey: boolean): Tool | null {
  if (role === 'interviewer') return 'cloud'
  if (role === 'limits') return jevKey ? 'jev' : 'laya'
  if (role === 'classification') return jevKey ? 'jev' : null
  return null
}

function RecommendedBadge({ it }: { it: boolean }) {
  return (
    <Badge variant="secondary" className="ml-1.5 align-middle text-[10px] font-medium">
      {it ? 'Consigliato' : 'Recommended'}
    </Badge>
  )
}

function reasonText(reason: string, it: boolean) {
  const messages: Record<string, [string, string]> = {
    ready: ['Disponibile', 'Available'],
    model_missing: ['Modello non disponibile', 'Model unavailable'],
    sign_in_required: ['Accedi con ChatGPT', 'Sign in with ChatGPT'],
    loading: ['Caricamento del modello', 'Loading model'],
    model_invalid: ['Modello da reinstallare', 'Reinstall model'],
    key_missing: ['Aggiungi la chiave API di Jev', 'Add a Jev API key'],
    not_evaluated: ['Non ancora valutato', 'Not evaluated yet'],
  }
  return messages[reason]?.[it ? 0 : 1] ?? (it ? 'Non disponibile' : 'Unavailable')
}

function useExecution() {
  return useQuery({
    queryKey: QUERY_KEY,
    queryFn: api.executionProfile,
    refetchInterval: (query) =>
      query.state.data?.locked ||
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
  const [jevKey, setJevKey] = useState('')
  const saveJev = useMutation({
    mutationFn: api.saveJevKey,
    onSuccess: (view) => {
      setJevKey('')
      update(view)
    },
  })
  const removeJev = useMutation({ mutationFn: api.removeJevKey, onSuccess: update })
  const reconstruct = useMutation({ mutationFn: api.setAnswerReconstruction, onSuccess: update })
  const signIn = useMutation({
    mutationFn: api.chatGptSignIn,
    onSuccess: ({ url }) => {
      window.location.assign(url)
    },
  })
  const account = execution.data?.chatgpt
  const busy =
    select.isPending ||
    signIn.isPending ||
    signOut.isPending ||
    saveJev.isPending ||
    removeJev.isPending ||
    reconstruct.isPending
  const error =
    execution.error ??
    select.error ??
    signIn.error ??
    signOut.error ??
    removeJev.error ??
    reconstruct.error
  const cloud = execution.data?.tools.some((role) => role.selected === 'cloud')
  const jevSelected = execution.data?.tools.some((role) => role.selected === 'jev')
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
                  {role.id === 'classification' && role.selected === 'jev' && (
                    <p className="mt-2 text-xs text-muted-foreground">
                      {it
                        ? 'Le righe dei requisiti delle offerte vengono inviate a TypeSafe. Se Jev non risponde, l’analisi si ferma fino al ripristino.'
                        : 'The requirement lines of job offers are sent to TypeSafe. If Jev does not answer, the analysis stops until it is restored.'}
                    </p>
                  )}
                  {role.id === 'limits' &&
                    (role.selected === 'laya' || role.selected === 'jev') && (
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
                            {choice.id === recommended(role.id, execution.data.jev.configured) && (
                              <RecommendedBadge it={it} />
                            )}
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
                  {option && modelLabel(role.selected, option.model_ref) && (
                    <p className="break-all text-xs text-muted-foreground">
                      {modelLabel(role.selected, option.model_ref)}
                    </p>
                  )}
                </div>
                {role.id === 'interviewer' && (
                  <label
                    htmlFor="answer-reconstruction"
                    className="flex w-full items-start justify-between gap-4 rounded-xl border bg-muted/20 p-4 text-sm sm:col-span-2"
                  >
                    <span className="min-w-0">
                      <span className="font-medium">
                        {it ? 'Trascrizione ricostruita' : 'Reconstructed transcript'}
                      </span>
                      {role.selected === 'cloud' && <RecommendedBadge it={it} />}
                      <span
                        id="answer-reconstruction-description"
                        className="mt-1 block text-muted-foreground"
                      >
                        {it
                          ? 'Dopo ogni risposta, ChatGPT ne riscrive il testo correggendo gli errori di riconoscimento. Il testo live e l’audio restano scaricabili, e prima del report puoi correggere tutto a mano.'
                          : 'After each answer, ChatGPT rewrites its text, fixing recognition errors. The live text and the audio stay downloadable, and you can edit everything before the report.'}
                      </span>
                      {role.selected !== 'cloud' && (
                        <span className="mt-1 block text-xs text-muted-foreground">
                          {it
                            ? 'Disponibile con ChatGPT come intervistatore: nei test i modelli locali riformulavano le risposte e inventavano numeri.'
                            : 'Available with ChatGPT as the interviewer: in tests, local models rephrased answers and invented figures.'}
                        </span>
                      )}
                    </span>
                    <Switch
                      id="answer-reconstruction"
                      data-testid="answer-reconstruction"
                      aria-label={it ? 'Trascrizione ricostruita' : 'Reconstructed transcript'}
                      aria-describedby="answer-reconstruction-description"
                      checked={execution.data.answer_reconstruction.enabled}
                      disabled={busy || execution.data.locked || role.selected !== 'cloud'}
                      onCheckedChange={(checked) => {
                        reconstruct.mutate(checked)
                      }}
                    />
                  </label>
                )}
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
        <section
          aria-label={it ? 'Servizio Jev' : 'Jev service'}
          className="rounded-xl border bg-muted/20 p-4"
        >
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div className="max-w-md">
              <h3 className="flex items-center gap-2 text-sm font-semibold">
                <ZapIcon className="size-4" aria-hidden="true" />
                {it ? 'Jev di TypeSafe (facoltativo)' : 'TypeSafe Jev (optional)'}
                {execution.data?.jev.configured && (
                  <Badge variant="outline">{it ? 'Chiave salvata' : 'Key saved'}</Badge>
                )}
              </h3>
              <p className="mt-1 text-sm text-muted-foreground">
                {it
                  ? 'Un servizio cloud che può leggere i limiti dichiarati al posto di Laya, utile se Laya non è installato. Richiede una chiave API a consumo.'
                  : 'A cloud service that can read stated limits instead of Laya, useful when Laya is not installed. It needs a pay-as-you-go API key.'}{' '}
                <a
                  href={TYPESAFE_CONSOLE_URL}
                  target="_blank"
                  rel="noreferrer"
                  className="underline"
                >
                  {it ? 'Console TypeSafe' : 'TypeSafe console'}
                </a>
              </p>
            </div>
            {execution.data?.jev.configured && (
              <Button
                variant="outline"
                size="sm"
                disabled={busy || execution.data.locked}
                onClick={() => {
                  removeJev.mutate()
                }}
              >
                {it ? 'Rimuovi la chiave' : 'Remove key'}
              </Button>
            )}
          </div>
          <form
            className="mt-4 flex flex-wrap items-end gap-3"
            onSubmit={(event) => {
              event.preventDefault()
              saveJev.mutate(jevKey)
            }}
          >
            <div className="w-full min-w-0 space-y-2 sm:w-auto sm:flex-1">
              <Label htmlFor="jev-key">
                {execution.data?.jev.configured
                  ? it
                    ? 'Sostituisci la chiave API'
                    : 'Replace the API key'
                  : it
                    ? 'Chiave API di Jev'
                    : 'Jev API key'}
              </Label>
              <Input
                id="jev-key"
                type="password"
                autoComplete="off"
                spellCheck={false}
                value={jevKey}
                disabled={busy || execution.data?.locked}
                onChange={(event) => {
                  setJevKey(event.target.value)
                }}
              />
            </div>
            <Button type="submit" disabled={busy || execution.data?.locked || !jevKey.trim()}>
              <KeyRoundIcon aria-hidden="true" />
              {it ? 'Verifica e salva' : 'Verify and save'}
            </Button>
          </form>
          {saveJev.error && (
            <p role="alert" className="mt-2 text-sm text-destructive">
              {saveJev.error.message}
            </p>
          )}
          {jevSelected && (
            <p role="note" className="mt-3 border-t pt-3 text-sm text-muted-foreground">
              {it
                ? 'Con Jev, la domanda dell’intervistatore e la tua risposta vengono inviate a TypeSafe a ogni turno.'
                : 'With Jev, the interviewer’s question and your answer are sent to TypeSafe on every turn.'}
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
            {settingsLockMessage(execution.data.lock_reason, it ? 'it' : 'en')}
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
