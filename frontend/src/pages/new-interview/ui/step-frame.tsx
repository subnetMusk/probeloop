import { Link, Outlet, useNavigate } from '@tanstack/react-router'
import { ArrowLeftIcon, ArrowRightIcon, CheckIcon } from 'lucide-react'
import type { ReactNode } from 'react'
import { cn } from 'cn'

import { STEPS, applies, canOpen, previousStep, stepDone, useDraft } from '@/entities/preparation'
import type { Step } from '@/entities/preparation'
import { useMessages } from '@/shared/i18n'
import { Button } from '@/shared/ui/button'
import { Page, PageHeader } from '@/shared/ui/page-header'
import { stepPath } from '../model/paths'
import { newInterviewMessages } from './messages'

/** The steps of the preparation: done steps and the next one open; skipped ones say so. */
function Stepper({ current }: { current: Step | undefined }) {
  const t = useMessages(newInterviewMessages)
  const draft = useDraft()
  return (
    <nav aria-label={t.stepper}>
      <ol className="flex flex-wrap gap-x-2 gap-y-2 text-sm">
        {STEPS.map((step, index) => {
          const skipped = !applies(draft, step)
          const done = !skipped && stepDone(draft, step)
          const here = step === current
          const label = (
            <>
              <span
                className={cn(
                  'flex size-6 shrink-0 items-center justify-center rounded-full border text-xs font-semibold',
                  here && 'border-brand bg-brand text-brand-foreground',
                  done && !here && 'border-brand text-brand-text',
                )}
                aria-hidden="true"
              >
                {done && !here ? <CheckIcon className="size-3.5" /> : index + 1}
              </span>
              <span className={cn(skipped && 'line-through')}>{t.steps[step].name}</span>
              {skipped && <span className="sr-only">({t.skipped})</span>}
            </>
          )
          return (
            <li key={step} className="flex items-center gap-2">
              {index > 0 && <span aria-hidden="true" className="h-px w-4 bg-border" />}
              {!here && canOpen(draft, step) ? (
                <Link
                  to={stepPath(step)}
                  className="flex items-center gap-2 rounded-md px-1.5 py-1 hover:bg-muted"
                >
                  {label}
                </Link>
              ) : (
                <span
                  aria-current={here ? 'step' : undefined}
                  className={cn(
                    'flex items-center gap-2 px-1.5 py-1',
                    here ? 'font-medium text-foreground' : 'text-muted-foreground',
                  )}
                >
                  {label}
                </span>
              )}
            </li>
          )
        })}
      </ol>
    </nav>
  )
}

/** The layout of the preparation: the stepper above the current step. */
export function NewInterviewLayout() {
  return (
    <Page>
      <Outlet />
    </Page>
  )
}

/** One step: stepper, title, the step's content, and its navigation. */
export function StepFrame({
  step,
  required = false,
  children,
  footer,
}: {
  step: Step
  required?: boolean
  children: ReactNode
  footer: ReactNode
}) {
  const t = useMessages(newInterviewMessages)
  const draft = useDraft()
  const applicable = STEPS.filter((s) => applies(draft, s))
  const position = applicable.indexOf(step) + 1
  return (
    <>
      <Stepper current={step} />
      <PageHeader
        eyebrow={t.eyebrow(position, applicable.length)}
        title={t.steps[step].title}
        description={t.steps[step].description}
      >
        {required && <p className="text-sm text-muted-foreground">{t.required}</p>}
      </PageHeader>
      {children}
      {footer}
    </>
  )
}

/**
 * Back is always allowed and keeps what was entered; Continue waits until the step has what it
 * needs, and the hint says what is missing.
 */
export function StepFooter({
  step,
  hint,
  disabled,
  pending = false,
  form,
  label,
  onContinue,
}: {
  step: Step
  hint?: string
  disabled: boolean
  pending?: boolean
  /** The id of the form that Continue submits. */
  form?: string
  label?: string
  onContinue?: () => void
}) {
  const t = useMessages(newInterviewMessages)
  const navigate = useNavigate()
  const draft = useDraft()
  const back = previousStep(draft, step)
  return (
    <div
      data-sticky-bar
      className="sticky bottom-0 z-10 -mx-6 flex flex-wrap items-center justify-between gap-3 border-t bg-background/95 px-6 py-4 backdrop-blur"
    >
      {back ? (
        <Button
          type="button"
          variant="outline"
          disabled={pending}
          onClick={() => void navigate({ to: stepPath(back) })}
        >
          <ArrowLeftIcon data-icon="inline-start" />
          {t.back}
        </Button>
      ) : (
        <span />
      )}
      <div className="flex flex-wrap items-center justify-end gap-3">
        {hint && (
          <p id="step-hint" className="text-sm text-muted-foreground">
            {hint}
          </p>
        )}
        <Button
          type={form ? 'submit' : 'button'}
          form={form}
          size="lg"
          disabled={disabled || pending}
          aria-describedby={hint ? 'step-hint' : undefined}
          data-testid="step-continue"
          onClick={form ? undefined : onContinue}
        >
          {label ?? t.continue}
          <ArrowRightIcon data-icon="inline-end" />
        </Button>
      </div>
    </div>
  )
}
