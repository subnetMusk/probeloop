import { useQuery } from '@tanstack/react-query'
import { Link } from '@tanstack/react-router'
import { LoaderCircleIcon } from 'lucide-react'
import { useState } from 'react'

import { useDraft } from '@/entities/preparation'
import { CvCheck } from '@/features/check-cv'
import { MicrophoneCheck, useVoiceReadiness } from '@/features/check-microphone'
import { useStartInterview } from '@/features/start-interview'
import { api } from '@/shared/api'
import { useMessages } from '@/shared/i18n'
import { Alert, AlertDescription, AlertTitle } from '@/shared/ui/alert'
import { Card, CardContent, CardHeader, CardTitle } from '@/shared/ui/card'
import { Progress } from '@/shared/ui/progress'
import { newInterviewMessages } from './messages'
import { stepPath } from '../model/paths'
import { StepFooter, StepFrame } from './step-frame'

function Summary() {
  const t = useMessages(newInterviewMessages)
  const draft = useDraft()
  const { settings, profile } = draft
  const documents =
    profile?.kind === 'quick'
      ? t.summary.quick
      : profile?.kind === 'saved' || profile?.kind === 'new'
        ? profile.name
        : t.summary.once
  const rows: [
    string,
    string,
    // The processing tools were fixed when the analysis started; Settings change later work.
    'interview-settings' | 'resource-profile' | 'fact-review' | null,
  ][] = [
    [t.summary.type, t.summary.types[settings.interviewType], 'interview-settings'],
    [t.summary.difficulty, t.summary.difficulties[settings.difficulty], 'interview-settings'],
    [t.summary.language, t.summary.languages[settings.language], 'interview-settings'],
    [t.summary.duration, `${String(settings.minutes)} min`, 'interview-settings'],
    [
      t.summary.processing,
      settings.execution?.startsWith('{')
        ? t.summary.mixed
        : settings.execution === 'cloud'
          ? t.summary.cloud
          : t.summary.local,
      null,
    ],
    [t.summary.profile, documents, 'resource-profile'],
  ]
  if (draft.roleProfile)
    rows.push(
      [t.summary.targetRole, draft.roleProfile.target_role, 'fact-review'],
      [t.summary.level, draft.roleProfile.seniority, 'fact-review'],
    )
  return (
    <Card>
      <CardHeader>
        <CardTitle role="heading" aria-level={2}>
          {t.summary.title}
        </CardTitle>
      </CardHeader>
      <CardContent>
        <dl className="grid grid-cols-[auto_1fr_auto] gap-x-4 gap-y-2 text-sm">
          {rows.map(([label, value, step]) => (
            <div key={label} className="contents">
              <dt className="text-muted-foreground">{label}</dt>
              <dd className="font-medium">{value}</dd>
              <dd>
                {step === null ? (
                  <span className="text-xs text-muted-foreground">{t.summary.fixed}</span>
                ) : (
                  <Link
                    to={stepPath(step)}
                    aria-label={`${t.summary.edit}: ${label}`}
                    className="text-brand-text underline"
                  >
                    {t.summary.edit}
                  </Link>
                )}
              </dd>
            </div>
          ))}
        </dl>
      </CardContent>
    </Card>
  )
}

export function CheckStep() {
  const t = useMessages(newInterviewMessages)
  const draft = useDraft()
  const [cvBusy, setCvBusy] = useState(false)
  const readiness = useVoiceReadiness(draft.settings.language)
  const background = useQuery({
    queryKey: ['pending-jobs'],
    queryFn: api.pendingJobs,
    refetchInterval: 3000,
  })
  const start = useStartInterview()
  const kinds: Record<string, string> = t.background.kinds
  const snapshotId = draft.profile?.kind === 'quick' ? null : draft.snapshotId
  // The CV check of this preparation shows its own progress on this page.
  const others = (background.data ?? []).filter(
    (job) => !(job.kind === 'review_cv' && job.subject_id === snapshotId),
  )
  const busy = cvBusy || (background.data?.length ?? 0) > 0
  const missing = [
    readiness.audio.kit === null && t.missing.microphone,
    readiness.speech.data?.ready !== true && t.missing.speech,
    readiness.speech.data?.ready === true && readiness.voice === null && t.missing.voice,
    busy && t.missing.busy,
  ].filter((text): text is string => typeof text === 'string')
  return (
    <StepFrame
      step="final-check"
      footer={
        <StepFooter
          step="final-check"
          label={start.isPending ? t.starting : t.start}
          disabled={!readiness.ready || busy || background.data === undefined}
          pending={start.isPending}
          hint={missing.join(' ') || undefined}
          onContinue={() => {
            start.mutate()
          }}
        />
      }
    >
      {others.length > 0 && (
        <Alert role="status" data-testid="background-work">
          <LoaderCircleIcon className="animate-spin text-brand-text" />
          <AlertTitle>{t.background.title}</AlertTitle>
          <AlertDescription>
            <p>{t.background.note}</p>
            <ul className="mt-3 flex w-full flex-col gap-3">
              {others.map((job) => (
                <li key={job.id} className="flex flex-col gap-1.5">
                  <div className="flex items-center justify-between gap-3 text-sm text-foreground">
                    <span>{kinds[job.kind] ?? t.background.other}</span>
                    <span className="text-xs text-muted-foreground tabular-nums">
                      {job.status === 'queued'
                        ? t.background.queued
                        : `${String(Math.round(job.progress * 100))}%`}
                    </span>
                  </div>
                  <Progress
                    value={job.progress * 100}
                    aria-label={kinds[job.kind] ?? t.background.other}
                  />
                </li>
              ))}
            </ul>
          </AlertDescription>
        </Alert>
      )}
      <div className="grid gap-6 lg:grid-cols-[3fr_2fr]">
        <div className="flex flex-col gap-6">
          {snapshotId && (
            <CvCheck
              snapshotId={snapshotId}
              language={draft.settings.language}
              execution={draft.settings.execution ?? 'local'}
              profileId={draft.profile?.kind === 'saved' ? draft.profile.id : null}
              inInterview
              onBusyChange={setCvBusy}
            />
          )}
          <Summary />
        </div>
        <MicrophoneCheck language={draft.settings.language} />
      </div>
      {start.error && (
        <Alert variant="destructive">
          <AlertTitle>{t.startFailed}</AlertTitle>
          <AlertDescription>{start.error.message}</AlertDescription>
        </Alert>
      )}
    </StepFrame>
  )
}
