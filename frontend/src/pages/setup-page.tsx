import { useMutation, useQuery } from '@tanstack/react-query'
import { useNavigate } from '@tanstack/react-router'
import { MicIcon } from 'lucide-react'
import { useState } from 'react'

import { api } from '@/api/rest'
import type { CreateSession } from '@/api/rest'
import { PROBLEM_TEXT, useAudio } from '@/audio/audio-state'
import { LevelMeter } from '@/components/level-meter'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Label } from '@/components/ui/label'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'

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

function Choice<T extends string>(props: {
  id: string
  label: string
  value: T
  options: Record<T, string> | Record<string, string>
  disabled?: (value: string) => boolean
  onChange: (value: T) => void
}) {
  return (
    <div className="flex flex-col gap-2">
      <Label htmlFor={props.id}>{props.label}</Label>
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
              {text}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
    </div>
  )
}

/** Choose the interview, check the microphone and the speech services, then start. */
export function SetupPage() {
  const navigate = useNavigate()
  const audio = useAudio()
  const [type, setType] = useState<InterviewType>('technical')
  const [difficulty, setDifficulty] = useState<Difficulty>('medium')
  const [language, setLanguage] = useState<Language>('it')
  const [minutes, setMinutes] = useState('10')

  const speech = useQuery({
    queryKey: ['speech-status'],
    queryFn: api.speechStatus,
    refetchInterval: (query) => (query.state.data?.ready ? false : 5000),
  })
  const create = useMutation({
    mutationFn: api.createSession,
    onSuccess: (session) => {
      void navigate({ to: '/interview/$sessionId', params: { sessionId: session.id } })
    },
  })

  const voices = speech.data?.voices ?? {}
  const canStart = audio.kit !== null && !create.isPending

  return (
    <div className="mx-auto grid max-w-4xl gap-6 p-6 md:grid-cols-2">
      <Card>
        <CardHeader>
          <CardTitle>New voice interview</CardTitle>
          <CardDescription>The interviewer speaks; you answer out loud.</CardDescription>
        </CardHeader>
        <CardContent className="flex flex-col gap-4">
          <Choice
            id="type"
            label="Interview type"
            value={type}
            options={TYPES}
            onChange={setType}
          />
          <Choice
            id="difficulty"
            label="Difficulty"
            value={difficulty}
            options={DIFFICULTIES}
            onChange={setDifficulty}
          />
          <Choice
            id="language"
            label="Language"
            value={language}
            options={LANGUAGES}
            disabled={(value) => !voices[value]}
            onChange={setLanguage}
          />
          <Choice
            id="minutes"
            label="Duration"
            value={minutes}
            options={Object.fromEntries(DURATIONS.map((m) => [String(m), `${m} minutes`]))}
            onChange={setMinutes}
          />
        </CardContent>
      </Card>

      <div className="flex flex-col gap-6">
        <Card>
          <CardHeader>
            <CardTitle>Microphone check</CardTitle>
            <CardDescription>Speak: the bar should move with your voice.</CardDescription>
          </CardHeader>
          <CardContent className="flex flex-col gap-4">
            {audio.kit ? (
              <>
                <div className="text-sm text-muted-foreground">{audio.kit.microphone.label}</div>
                <LevelMeter dbfs={audio.level} />
              </>
            ) : (
              <Button onClick={() => void audio.enable()} disabled={audio.enabling}>
                <MicIcon data-icon="inline-start" />
                {audio.enabling ? 'Enabling…' : 'Enable microphone'}
              </Button>
            )}
            {audio.problem && (
              <Alert variant="destructive">
                <AlertTitle>Microphone unavailable</AlertTitle>
                <AlertDescription>{PROBLEM_TEXT[audio.problem]}</AlertDescription>
              </Alert>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Speech services</CardTitle>
            <CardDescription>
              {speech.data?.ready ? (
                <Badge variant="secondary">ready</Badge>
              ) : (
                <Badge variant="outline">not ready yet</Badge>
              )}
            </CardDescription>
          </CardHeader>
          <CardContent className="flex flex-col gap-2 text-sm">
            {speech.data?.problems.map((problem) => (
              <div key={problem} className="text-muted-foreground">
                {problem}
              </div>
            ))}
            {speech.error && <div className="text-destructive">The backend is not reachable.</div>}
            <div className="text-xs text-muted-foreground">
              Starting waits for services that are still loading.
            </div>
          </CardContent>
        </Card>

        <Button
          size="lg"
          disabled={!canStart}
          onClick={() => {
            create.mutate({
              interview_type: type,
              difficulty,
              language,
              modality: 'voice',
              duration_minutes: Number(minutes),
            })
          }}
        >
          Start interview
        </Button>
        {create.error && (
          <Alert variant="destructive">
            <AlertTitle>The interview could not be created</AlertTitle>
            <AlertDescription>{create.error.message}</AlertDescription>
          </Alert>
        )}
      </div>
    </div>
  )
}
