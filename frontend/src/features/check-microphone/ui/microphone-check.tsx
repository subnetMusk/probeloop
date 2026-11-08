import { CheckCircle2Icon, CircleAlertIcon, Loader2Icon, MicIcon } from 'lucide-react'
import type { ReactNode } from 'react'

import { defineMessages, localise, useMessages } from '@/shared/i18n'
import { PROBLEM_TEXT } from '@/shared/lib/audio'
import { Alert, AlertDescription, AlertTitle } from '@/shared/ui/alert'
import { Button } from '@/shared/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/shared/ui/card'
import { LevelMeter } from '@/shared/ui/level-meter'
import { useVoiceReadiness } from '../model/readiness'

const messages = defineMessages({
  en: {
    title: 'Microphone and voice',
    description: 'Use headphones if you can: it avoids echo.',
    enable: 'Enable microphone',
    enabling: 'Enabling…',
    microphone: 'Microphone',
    speak: 'Say something: the bar should move with your voice.',
    unavailable: 'Microphone unavailable',
    speech: 'Speech recognition and voice',
    voice: 'Interviewer voice for the chosen language',
    unreachable: 'The backend is not reachable.',
    credits: 'Speech synthesis by Piper, recognition by Parakeet, both running locally.',
    voiceCredit: (credit: string) => `Interviewer voice: ${credit}.`,
  },
  it: {
    title: 'Microfono e voce',
    description: 'Se puoi usa le cuffie: evitano l’eco.',
    enable: 'Attiva il microfono',
    enabling: 'Attivazione…',
    microphone: 'Microfono',
    speak: 'Di’ qualcosa: la barra deve muoversi con la tua voce.',
    unavailable: 'Microfono non disponibile',
    speech: 'Riconoscimento vocale e voce',
    voice: 'Voce dell’intervistatore per la lingua scelta',
    unreachable: 'Il backend non è raggiungibile.',
    credits: 'Sintesi vocale di Piper, riconoscimento di Parakeet, entrambi in locale.',
    voiceCredit: (credit: string) => `Voce dell’intervistatore: ${credit}.`,
  },
})

// Piper voices need attribution under their licence (ADR 0010).
const VOICE_CREDITS: Record<string, string> = {
  'it_IT-serena-medium': 'serena (Piper), CC BY 4.0',
  'it_IT-paola-medium': 'paola (Piper), CC0',
}

function Check({ ok, pending, children }: { ok: boolean; pending?: boolean; children: ReactNode }) {
  let icon = <CircleAlertIcon className="size-4 text-warning" aria-hidden="true" />
  if (pending) icon = <Loader2Icon className="size-4 animate-spin" aria-hidden="true" />
  else if (ok) icon = <CheckCircle2Icon className="size-4 text-success" aria-hidden="true" />
  return (
    <li className="flex items-center gap-2 text-sm" data-ok={ok}>
      {icon}
      <span className={ok ? '' : 'text-muted-foreground'}>{children}</span>
    </li>
  )
}

/** Enable the microphone, watch its level, and check the local speech services. */
export function MicrophoneCheck({ language }: { language: string }) {
  const t = useMessages(messages)
  const { audio, speech, voice } = useVoiceReadiness(language)
  return (
    <Card>
      <CardHeader>
        <CardTitle role="heading" aria-level={2} className="flex items-center gap-2">
          <MicIcon className="size-5 text-brand-text" aria-hidden="true" />
          {t.title}
        </CardTitle>
        <CardDescription>{t.description}</CardDescription>
      </CardHeader>
      <CardContent className="flex flex-col gap-5">
        {audio.kit ? (
          <div className="flex flex-col gap-2">
            <p className="truncate text-sm">{audio.kit.microphone.label || t.microphone}</p>
            <LevelMeter dbfs={audio.level} />
            <p className="text-xs text-muted-foreground">{t.speak}</p>
          </div>
        ) : (
          <Button
            type="button"
            variant="outline"
            className="self-start"
            onClick={() => void audio.enable()}
            disabled={audio.enabling}
            data-testid="enable-microphone"
          >
            <MicIcon data-icon="inline-start" />
            {audio.enabling ? t.enabling : t.enable}
          </Button>
        )}
        {audio.problem && (
          <Alert variant="destructive">
            <AlertTitle>{t.unavailable}</AlertTitle>
            <AlertDescription>{localise(PROBLEM_TEXT[audio.problem])}</AlertDescription>
          </Alert>
        )}
        <ul className="flex flex-col gap-2" data-testid="speech-status">
          <Check ok={audio.kit !== null}>{t.microphone}</Check>
          <Check ok={speech.data?.ready ?? false} pending={speech.isPending}>
            {t.speech}
          </Check>
          <Check ok={voice !== null} pending={speech.isPending}>
            {t.voice}
          </Check>
          {speech.data?.problems.map((problem) => (
            <li key={problem} className="pl-6 text-xs text-muted-foreground">
              {problem}
            </li>
          ))}
          {speech.error && <li className="pl-6 text-xs text-destructive">{t.unreachable}</li>}
        </ul>
        <p className="text-xs text-muted-foreground">
          {voice && `${t.voiceCredit(VOICE_CREDITS[voice] ?? voice)} `}
          {t.credits}
        </p>
      </CardContent>
    </Card>
  )
}
