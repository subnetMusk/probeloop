import { MicIcon, MicOffIcon } from 'lucide-react'
import type { ReactNode } from 'react'

import { cn } from '@/lib/utils'

interface ParticipantTileProps {
  name: string
  role: string
  initials: string
  tone: 'interviewer' | 'candidate'
  level: number // 0..1, drives the speaking rings
  speaking: boolean
  muted: boolean
  status?: ReactNode
  testId?: string
}

const AVATAR: Record<ParticipantTileProps['tone'], string> = {
  interviewer: 'from-indigo-500 to-violet-600',
  candidate: 'from-emerald-500 to-teal-600',
}

/** A participant in the call: avatar, speaking rings, name plate and microphone state. */
export function ParticipantTile(props: ParticipantTileProps) {
  const scale = 1 + props.level * 0.6
  return (
    <div
      data-testid={props.testId}
      data-speaking={props.speaking}
      className={cn(
        'relative flex min-h-56 items-center justify-center overflow-hidden rounded-2xl bg-zinc-900 ring-1 ring-white/5 transition-shadow duration-300',
        props.speaking &&
          'ring-2 ring-emerald-400/80 shadow-[0_0_40px_-10px] shadow-emerald-400/40',
      )}
    >
      <div className="absolute inset-0 bg-gradient-to-b from-white/[0.03] to-transparent" />
      <div className="relative flex items-center justify-center">
        <span
          aria-hidden
          className={cn(
            'absolute size-28 rounded-full bg-gradient-to-br opacity-30 blur-sm',
            AVATAR[props.tone],
          )}
          style={{ transform: `scale(${scale * 1.15})`, transition: 'transform 80ms linear' }}
        />
        <span
          aria-hidden
          className={cn(
            'absolute size-28 rounded-full bg-gradient-to-br opacity-40',
            AVATAR[props.tone],
          )}
          style={{ transform: `scale(${scale})`, transition: 'transform 80ms linear' }}
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
        aria-label={props.muted ? 'microphone off' : 'microphone on'}
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
