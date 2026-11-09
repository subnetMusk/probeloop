import {
  CaptionsIcon,
  MessageSquareTextIcon,
  MicIcon,
  PhoneOffIcon,
  SquareIcon,
} from 'lucide-react'
import type { ReactNode } from 'react'

import { Tooltip, TooltipContent, TooltipTrigger } from '@/shared/ui/tooltip'
import { cn } from '@/shared/lib/utils'
import { useMessages } from '@/shared/i18n'
import { meetingMessages } from './messages'

function RoundButton(props: {
  label: string
  onClick: () => void
  active?: boolean
  disabled?: boolean
  className?: string
  children: ReactNode
  testId?: string
}) {
  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <button
          type="button"
          aria-label={props.label}
          aria-pressed={props.active}
          data-testid={props.testId}
          disabled={props.disabled}
          onClick={props.onClick}
          className={cn(
            'flex size-12 items-center justify-center rounded-full bg-zinc-800 text-zinc-100 transition-colors hover:bg-zinc-700 focus-visible:ring-2 focus-visible:ring-white/50 focus-visible:outline-none disabled:cursor-not-allowed disabled:opacity-40 [&_svg]:size-5',
            props.active && 'bg-zinc-100 text-zinc-900 hover:bg-white',
            props.className,
          )}
        >
          {props.children}
        </button>
      </TooltipTrigger>
      <TooltipContent>{props.label}</TooltipContent>
    </Tooltip>
  )
}

interface ControlBarProps {
  clock: string
  recording: boolean
  answering: boolean
  canAnswer: boolean
  captions: boolean
  transcript: boolean
  onAnswer: () => void
  onEndAnswer: () => void
  onToggleCaptions: () => void
  onToggleTranscript: () => void
  onEndCall: () => void
}

/** The bottom bar of the call: timer, answer button, panels and end call. */
export function ControlBar(props: ControlBarProps) {
  const t = useMessages(meetingMessages)
  return (
    <div className="grid grid-cols-[1fr_auto_1fr] items-center gap-4 px-4 py-3">
      <div className="flex items-center gap-3 text-sm text-zinc-300">
        <span className="font-mono tabular-nums" data-testid="timer">
          {props.clock}
        </span>
        {props.recording && (
          <span className="flex items-center gap-1.5 text-xs text-red-400">
            <span className="size-2 animate-pulse rounded-full bg-red-500" />
            REC
          </span>
        )}
      </div>
      <div className="flex items-center gap-3">
        {props.answering ? (
          <button
            type="button"
            onClick={props.onEndAnswer}
            data-testid="end-answer"
            className="flex h-12 items-center gap-2 rounded-full bg-red-500 px-5 font-medium text-white transition-colors hover:bg-red-600 focus-visible:ring-2 focus-visible:ring-white/50 focus-visible:outline-none"
          >
            <SquareIcon className="size-4 fill-current" />
            {t.endAnswer}
          </button>
        ) : (
          <button
            type="button"
            onClick={props.onAnswer}
            disabled={!props.canAnswer}
            data-testid="answer"
            className="flex h-12 items-center gap-2 rounded-full bg-brand px-5 font-medium text-brand-foreground transition-colors hover:bg-brand/85 focus-visible:ring-2 focus-visible:ring-white/50 focus-visible:outline-none disabled:cursor-not-allowed disabled:bg-zinc-800 disabled:text-zinc-500"
          >
            <MicIcon className="size-5" />
            {t.answer}
          </button>
        )}
        <RoundButton label={t.captions} active={props.captions} onClick={props.onToggleCaptions}>
          <CaptionsIcon />
        </RoundButton>
        <RoundButton
          label={t.transcript}
          active={props.transcript}
          onClick={props.onToggleTranscript}
          testId="toggle-transcript"
        >
          <MessageSquareTextIcon />
        </RoundButton>
        <RoundButton
          label={t.endCall}
          onClick={props.onEndCall}
          className="w-16 bg-red-600 text-white hover:bg-red-700"
          testId="end-call"
        >
          <PhoneOffIcon />
        </RoundButton>
      </div>
      <div className="hidden justify-end text-xs text-zinc-500 md:flex">
        {(props.canAnswer || props.answering) && t.shortcut}
      </div>
    </div>
  )
}
