import { useQuery } from '@tanstack/react-query'
import { Link } from '@tanstack/react-router'
import { ArrowRightIcon, CheckIcon } from 'lucide-react'

import { speechStatusQuery } from '@/features/check-microphone'
import { api } from '@/shared/api'
import { defineMessages, useMessages } from '@/shared/i18n'
import { hideGettingStarted, useOnboarding } from '@/shared/lib/onboarding'
import { cn } from '@/shared/lib/utils'
import { Button } from '@/shared/ui/button'

const messages = defineMessages({
  en: {
    title: 'Getting started',
    progress: (done: number, total: number) => `${String(done)} of ${String(total)} done`,
    hide: 'Hide',
    steps: {
      speech: {
        title: 'Install the speech components',
        text: 'Speech recognition and the interviewer’s voice run on this computer.',
        action: 'Open Settings',
      },
      tools: {
        title: 'Choose where the models run',
        text: 'ChatGPT replies fastest; a local model keeps every text on this computer.',
        action: 'Choose the tools',
      },
      guide: {
        title: 'See how an interview works',
        text: 'Five minutes on the stages, the controls and the recommended settings.',
        action: 'Read the guide',
      },
      interview: {
        title: 'Practise your first interview',
        text: 'Add your CV and the job offer, check what the analysis understood, then answer aloud.',
        action: 'New interview',
      },
      report: {
        title: 'Read your first report',
        text: 'Review the transcript, correct flagged answers, then generate the report.',
        action: 'Open interviews',
      },
    },
  },
  it: {
    title: 'Primi passi',
    progress: (done: number, total: number) => `${String(done)} di ${String(total)} completati`,
    hide: 'Nascondi',
    steps: {
      speech: {
        title: 'Installa i componenti vocali',
        text: 'Riconoscimento vocale e voce dell’intervistatore girano su questo computer.',
        action: 'Apri le Impostazioni',
      },
      tools: {
        title: 'Scegli dove girano i modelli',
        text: 'ChatGPT risponde più in fretta; un modello locale tiene ogni testo su questo computer.',
        action: 'Scegli gli strumenti',
      },
      guide: {
        title: 'Scopri come funziona un colloquio',
        text: 'Cinque minuti su fasi, comandi e impostazioni consigliate.',
        action: 'Leggi la guida',
      },
      interview: {
        title: 'Fai il tuo primo colloquio',
        text: 'Aggiungi CV e offerta, controlla ciò che l’analisi ha capito, poi rispondi a voce.',
        action: 'Nuovo colloquio',
      },
      report: {
        title: 'Leggi il tuo primo report',
        text: 'Rivedi il trascritto, correggi le risposte segnalate, poi genera il report.',
        action: 'Apri i colloqui',
      },
    },
  },
})

type StepId = 'speech' | 'tools' | 'guide' | 'interview' | 'report'
const TARGET = {
  speech: '/settings',
  tools: '/settings',
  guide: '/guide',
  interview: '/new-interview',
  report: '/interviews',
} as const

/**
 * The first-run checklist (an empty state that teaches, rather than a tutorial): each step is
 * ticked from the application's real state and the next one carries the action to take.
 */
export function GettingStarted({ interviews, reports }: { interviews: number; reports: number }) {
  const t = useMessages(messages)
  const { guideSeen, hidden } = useOnboarding()
  const speech = useQuery(speechStatusQuery)
  const tools = useQuery({ queryKey: ['execution-profile'], queryFn: api.executionProfile })
  const toolsReady =
    tools.data?.tools.every(
      (role) => role.options.find((option) => option.id === role.selected)?.available === true,
    ) === true
  const done: Record<StepId, boolean> = {
    speech: speech.data?.ready === true,
    tools: toolsReady,
    guide: guideSeen,
    interview: interviews > 0,
    report: reports > 0,
  }
  const order: StepId[] = ['speech', 'tools', 'guide', 'interview', 'report']
  const completed = order.filter((id) => done[id]).length
  const next = order.find((id) => !done[id])
  if (hidden || next === undefined || speech.isPending || tools.isPending) return null
  return (
    <section
      aria-labelledby="getting-started-title"
      data-testid="getting-started"
      className="rounded-2xl border bg-card p-5 sm:p-6"
    >
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 id="getting-started-title" className="text-xl font-semibold">
            {t.title}
          </h2>
          <p className="mt-1 text-sm text-muted-foreground">
            {t.progress(completed, order.length)}
          </p>
        </div>
        <Button variant="ghost" size="sm" onClick={hideGettingStarted}>
          {t.hide}
        </Button>
      </div>
      <div
        role="progressbar"
        aria-label={t.title}
        aria-valuemin={0}
        aria-valuemax={order.length}
        aria-valuenow={completed}
        className="mt-4 flex gap-1.5"
      >
        {order.map((id) => (
          <span
            key={id}
            className={cn('h-1.5 flex-1 rounded-full', done[id] ? 'bg-brand' : 'bg-muted')}
          />
        ))}
      </div>
      <ol className="mt-5 flex flex-col gap-1">
        {order.map((id, index) => {
          const step = t.steps[id]
          const current = id === next
          return (
            <li
              key={id}
              data-state={done[id] ? 'done' : current ? 'current' : 'pending'}
              className={cn(
                'flex flex-wrap items-center gap-x-4 gap-y-2 rounded-xl px-3 py-3',
                current && 'bg-muted/60',
              )}
            >
              <span
                aria-hidden
                className={cn(
                  'flex size-7 shrink-0 items-center justify-center rounded-full text-sm font-semibold',
                  done[id]
                    ? 'bg-success/15 text-success'
                    : current
                      ? 'bg-brand text-brand-foreground'
                      : 'bg-muted text-muted-foreground',
                )}
              >
                {done[id] ? <CheckIcon className="size-4" strokeWidth={3} /> : index + 1}
              </span>
              <div className="min-w-0 flex-1">
                <p className={cn('font-medium', done[id] && 'text-muted-foreground line-through')}>
                  {step.title}
                </p>
                {!done[id] && <p className="text-sm text-muted-foreground">{step.text}</p>}
              </div>
              {current && (
                <Button
                  asChild
                  size="sm"
                  className="bg-brand text-brand-foreground hover:bg-brand/90"
                >
                  <Link to={TARGET[id]}>
                    {step.action}
                    <ArrowRightIcon data-icon="inline-end" />
                  </Link>
                </Button>
              )}
              {!current && !done[id] && (
                <Link
                  to={TARGET[id]}
                  className="text-sm text-brand-text underline-offset-4 hover:underline"
                >
                  {step.action}
                </Link>
              )}
            </li>
          )
        })}
      </ol>
    </section>
  )
}
