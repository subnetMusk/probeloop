import { useMutation, useQuery } from '@tanstack/react-query'
import { useNavigate } from '@tanstack/react-router'
import { CheckCircle2Icon, CircleAlertIcon, Loader2Icon, MicIcon, VideoIcon } from 'lucide-react'
import { useState } from 'react'
import type { ReactNode } from 'react'

import { api } from '@/api/rest'
import type { CreateSession } from '@/api/rest'
import { PROBLEM_TEXT, useAudio } from '@/audio/audio-state'
import { LevelMeter } from '@/components/level-meter'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Label } from '@/components/ui/label'
import { PREPARATION_KEY } from '@/context/setup-state'
import { CvReviewPanel } from '@/reports/cv-review-panel'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { T } from '@/settings/translated-text'
import { localise } from '@/settings/i18n'

type InterviewType = CreateSession['interview_type']
type Difficulty = NonNullable<CreateSession['difficulty']>
type Language = NonNullable<CreateSession['language']>

const TYPES: Record<InterviewType, string> = {
  technical: 'Technical',
  behavioral: 'Behavioural',
  hr: 'HR screening',
  mixed: 'Mixed',
}
const DIFFICULTIES: Record<Difficulty, string> = { easy: 'Easy', medium: 'Medium', hard: 'Hard' }
const LANGUAGES: Record<Language, string> = { it: 'Italian', en: 'English' }
const DURATIONS = [5, 10, 15, 20, 30]

// Piper voices need attribution under their licence (ADR 0010).
const VOICE_CREDITS: Record<string, string> = {
  'it_IT-serena-medium': 'serena (Piper), CC BY 4.0',
  'it_IT-paola-medium': 'paola (Piper), CC0',
}

function Choice<T extends string>(props: {
  id: string
  label: string
  value: T
  options: Record<string, string>
  disabled?: (value: string) => boolean
  onChange: (value: T) => void
}) {
  return (
    <div className="flex flex-col gap-2">
      <Label htmlFor={props.id}>
        <T text={props.label} />
      </Label>
      <Select
        value={props.value}
        onValueChange={(value) => {
          props.onChange(value as T)
        }}
      >
        <SelectTrigger id={props.id} className="w-full">
          <SelectValue />
        </SelectTrigger>
        <SelectContent>
          {Object.entries(props.options).map(([value, text]) => (
            <SelectItem key={value} value={value} disabled={props.disabled?.(value)}>
              <T text={text} />
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
    </div>
  )
}

function Check({ ok, pending, children }: { ok: boolean; pending?: boolean; children: ReactNode }) {
  let icon = <CircleAlertIcon className="size-4 text-amber-600" />
  if (pending) icon = <Loader2Icon className="size-4 animate-spin text-muted-foreground" />
  else if (ok) icon = <CheckCircle2Icon className="size-4 text-emerald-600" />
  return (
    <li className="flex items-center gap-2 text-sm">
      {icon}
      <span className={ok ? '' : 'text-muted-foreground'}>{children}</span>
    </li>
  )
}

/** Choose the interview, check the microphone and the speech services, then join the call. */
export function InterviewSetup({
  snapshotId,
  initialLanguage = 'it',
  gettingToKnow = false,
  onBack,
}: {
  snapshotId?: string
  initialLanguage?: Language
  gettingToKnow?: boolean
  onBack: () => void
}) {
  const navigate = useNavigate()
  const audio = useAudio()
  const [type, setType] = useState<InterviewType>(gettingToKnow ? 'hr' : 'technical')
  const [difficulty, setDifficulty] = useState<Difficulty>('medium')
  const [language, setLanguage] = useState<Language>(initialLanguage)
  const [minutes, setMinutes] = useState('10')
  const [reviewBusy, setReviewBusy] = useState(false)
  const processing = useQuery({
    queryKey: ['pending-jobs'],
    queryFn: api.pendingJobs,
    refetchInterval: 3000,
  })

  // The privacy statement depends on where the language models run.
  const execution = useQuery({ queryKey: ['execution-profile'], queryFn: api.executionProfile })
  const speech = useQuery({
    queryKey: ['speech-status'],
    queryFn: api.speechStatus,
    refetchInterval: (query) => (query.state.data?.ready ? false : 5000),
  })
  const create = useMutation({
    mutationFn: api.createSession,
    onSuccess: (session) => {
      sessionStorage.removeItem(PREPARATION_KEY)
      void navigate({ to: '/interview/$sessionId', params: { sessionId: session.id } })
    },
  })

  const voices = speech.data?.voices ?? {}
  const voice = voices[language]
  const canStart =
    audio.kit !== null &&
    speech.data?.ready === true &&
    Boolean(voice) &&
    !create.isPending &&
    !reviewBusy &&
    processing.data?.length === 0

  return (
    <div className="bg-gradient-to-b from-indigo-50/60 to-background dark:from-indigo-950/30">
      <div className="mx-auto flex max-w-5xl flex-col gap-8 px-6 py-10">
        <div className="flex flex-col gap-2">
          <Button variant="ghost" className="self-start" onClick={onBack}>
            <T text={'Back to preparation'} />
          </Button>
          <h1 className="font-heading text-3xl font-semibold tracking-tight">
            <T text={'Practise a job interview, out loud'} />
          </h1>
          <p className="max-w-2xl text-muted-foreground">
            <T
              text={
                execution.data?.profile === 'cloud'
                  ? 'An AI interviewer asks the questions and follows up on your answers. Your voice stays on this computer; the transcript, your documents and the answers are sent to OpenAI through your ChatGPT plan.'
                  : 'An AI interviewer asks the questions and follows up on your answers. Everything runs on this computer: your voice and the transcript stay here.'
              }
            />
          </p>
        </div>

        {snapshotId && <CvReviewPanel snapshotId={snapshotId} onBusyChange={setReviewBusy} />}
        <div className="grid gap-6 md:grid-cols-[3fr_2fr]">
          <Card>
            <CardHeader>
              <CardTitle>
                <T text={'Interview'} />
              </CardTitle>
              <CardDescription>
                <T text={'What kind of interview to practise.'} />
              </CardDescription>
            </CardHeader>
            <CardContent className="grid gap-4 sm:grid-cols-2">
              <Choice
                id="type"
                label={localise('Type')}
                value={type}
                options={TYPES}
                onChange={setType}
              />
              <Choice
                id="difficulty"
                label={localise('Difficulty')}
                value={difficulty}
                options={DIFFICULTIES}
                onChange={setDifficulty}
              />
              <Choice
                id="language"
                label="Interview language"
                value={language}
                options={LANGUAGES}
                disabled={(value) => !voices[value]}
                onChange={setLanguage}
              />
              <Choice
                id="minutes"
                label={localise('Duration')}
                value={minutes}
                options={Object.fromEntries(DURATIONS.map((m) => [String(m), `${m} min`]))}
                onChange={setMinutes}
              />
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>
                <T text={'Check your setup'} />
              </CardTitle>
              <CardDescription>
                <T text={'Use headphones if you can: it avoids echo.'} />
              </CardDescription>
            </CardHeader>
            <CardContent className="flex flex-col gap-5">
              {audio.kit ? (
                <div className="flex flex-col gap-2">
                  <div className="flex items-center gap-2 text-sm">
                    <MicIcon className="size-4 text-emerald-600" />
                    <span className="truncate">{audio.kit.microphone.label || 'Microphone'}</span>
                  </div>
                  <LevelMeter dbfs={audio.level} />
                  <p className="text-xs text-muted-foreground">
                    <T text={'Say something: the bar should move with your voice.'} />
                  </p>
                </div>
              ) : (
                <Button
                  variant="outline"
                  onClick={() => void audio.enable()}
                  disabled={audio.enabling}
                  data-testid="enable-microphone"
                >
                  <MicIcon data-icon="inline-start" />
                  <T text={audio.enabling ? 'Enabling…' : 'Enable microphone'} />
                </Button>
              )}
              {audio.problem && (
                <Alert variant="destructive">
                  <AlertTitle>
                    <T text={'Microphone unavailable'} />
                  </AlertTitle>
                  <AlertDescription>{PROBLEM_TEXT[audio.problem]}</AlertDescription>
                </Alert>
              )}
              <ul className="flex flex-col gap-2" data-testid="speech-status">
                <Check ok={audio.kit !== null}>
                  <T text={'Microphone'} />
                </Check>
                <Check ok={speech.data?.ready ?? false} pending={speech.isPending}>
                  <T text={'Speech recognition and voice'} />
                </Check>
                {speech.data?.problems.map((problem) => (
                  <li key={problem} className="pl-6 text-xs text-muted-foreground">
                    {problem}
                  </li>
                ))}
                {speech.error && (
                  <li className="pl-6 text-xs text-destructive">
                    <T text={'The backend is not reachable.'} />
                  </li>
                )}
              </ul>
              {Boolean(processing.data?.length) && (
                <p role="status" className="text-sm text-muted-foreground">
                  {localise('Wait for background processing before joining.')}
                </p>
              )}
              <Button
                size="lg"
                className="h-11"
                disabled={!canStart}
                data-testid="start-interview"
                onClick={() => {
                  create.mutate({
                    interview_type: type,
                    difficulty,
                    language,
                    modality: 'voice',
                    duration_minutes: Number(minutes),
                    snapshot_id: snapshotId,
                  })
                }}
              >
                <VideoIcon data-icon="inline-start" />
                <T text={create.isPending ? 'Creating…' : 'Join the interview'} />
              </Button>
              {create.error && (
                <Alert variant="destructive">
                  <AlertTitle>
                    <T text={'The interview could not be created'} />
                  </AlertTitle>
                  <AlertDescription>{create.error.message}</AlertDescription>
                </Alert>
              )}
            </CardContent>
          </Card>
        </div>

        <footer className="text-xs text-muted-foreground">
          {voice && `${localise('Interviewer voice:')} ${VOICE_CREDITS[voice] ?? voice}. `}
          <T text={'Speech synthesis by Piper, recognition by Parakeet, both running locally.'} />
        </footer>
      </div>
    </div>
  )
}
