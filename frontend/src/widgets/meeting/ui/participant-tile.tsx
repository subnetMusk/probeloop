import { MicIcon, MicOffIcon } from 'lucide-react'
import type { ReactNode } from 'react'

import { cn } from '@/shared/lib/utils'
import { useMessages } from '@/shared/i18n'
import { meetingMessages } from './messages'
import { ProgressRing } from './step-progress'
import type { RingSegment } from './step-progress'
import { VoiceRing } from './voice-ring'
import type { SpectrumReader } from './voice-ring'

interface ParticipantTileProps {
  name: string
  role: string
  initials: string
  tone: 'interviewer' | 'candidate'
  level: number // 0..1, loudness: the glow behind the avatar grows with it
  speaking: boolean
  muted: boolean
  status?: ReactNode
  progress?: RingSegment[] | null // work in progress for this participant, drawn around the avatar
  voice?: SpectrumReader | null // the speaker's spectrum, drawn as bars around the avatar
  listening?: boolean // the other participant is speaking: a slow, quiet breathing
  testId?: string
}

const AVATAR: Record<ParticipantTileProps['tone'], string> = {
  interviewer: 'from-brand to-highlight',
  candidate: 'from-zinc-500 to-zinc-700',
}

/**
 * A participant in the call: avatar, voice bars, name plate and microphone state. While the
 * participant speaks, bars around the avatar follow the voice's frequencies and the glow follows
 * its loudness; while the interviewer works on a reply, a ring of steps shows how far it has gone.
 */
export function ParticipantTile(props: ParticipantTileProps) {
  const t = useMessages(meetingMessages)
  const scale = 1 + props.level * 0.35
  return (
    <div
      data-testid={props.testId}
      data-speaking={props.speaking}
      className={cn(
        'relative flex min-h-48 items-center justify-center overflow-hidden rounded-2xl md:min-h-56 bg-zinc-900 ring-1 ring-white/5 transition-shadow duration-300',
        props.speaking && 'ring-2 ring-brand-text/80 shadow-[0_0_40px_-10px] shadow-brand-text/40',
      )}
    >
      <div className="absolute inset-0 bg-gradient-to-b from-white/[0.03] to-transparent" />
      <div className="relative flex scale-[0.8] items-center justify-center md:scale-100">
        {props.progress && (
          <ProgressRing
            segments={props.progress}
            className="absolute top-1/2 left-1/2 size-40 -translate-x-1/2 -translate-y-1/2 motion-safe:animate-in motion-safe:fade-in motion-safe:zoom-in-95"
          />
        )}
        {!props.progress && (
          <VoiceRing
            read={props.voice ?? null}
            active={props.speaking}
            tone={props.tone}
            innerRadius={66}
            className="absolute top-1/2 left-1/2 size-56 -translate-x-1/2 -translate-y-1/2"
          />
        )}
        <span
          aria-hidden
          className={cn(
            'absolute size-28 rounded-full bg-gradient-to-br blur-md transition-opacity duration-500',
            AVATAR[props.tone],
            props.speaking ? 'opacity-50' : 'opacity-25',
            (props.progress || props.listening) &&
              'motion-safe:animate-[pulse_3s_ease-in-out_infinite]',
          )}
          style={{ transform: `scale(${scale * 1.12})`, transition: 'transform 90ms linear' }}
        />
        <div
          className={cn(
            'relative flex size-28 items-center justify-center rounded-full bg-gradient-to-br text-3xl font-semibold text-white shadow-lg',
            AVATAR[props.tone],
          )}
        >
          {props.initials}
        </div>
      </div>
      {props.status && (
        <div className="absolute top-3 left-3 rounded-full bg-black/50 px-3 py-1 text-xs text-zinc-200 backdrop-blur">
          {props.status}
        </div>
      )}
      <div className="absolute bottom-3 left-3 flex items-center gap-2 rounded-lg bg-black/50 px-2.5 py-1.5 text-sm text-white backdrop-blur">
        <span className="font-medium">{props.name}</span>
        <span className="text-zinc-400">{props.role}</span>
      </div>
      <div
        className={cn(
          'absolute right-3 bottom-3 flex size-8 items-center justify-center rounded-full backdrop-blur',
          props.muted ? 'bg-red-500/80 text-white' : 'bg-black/50 text-white',
        )}
        aria-label={props.muted ? t.micOff : t.micOn}
      >
        {props.muted ? <MicOffIcon className="size-4" /> : <MicIcon className="size-4" />}
      </div>
    </div>
  )
}

/** Three dots that pulse, for "thinking" and "transcribing". */
export function Dots() {
  return (
    <span className="ml-1 inline-flex gap-0.5 align-middle">
      {[0, 150, 300].map((delay) => (
        <span
          key={delay}
          className="size-1 animate-pulse rounded-full bg-current"
          style={{ animationDelay: `${delay}ms` }}
        />
      ))}
    </span>
  )
}
