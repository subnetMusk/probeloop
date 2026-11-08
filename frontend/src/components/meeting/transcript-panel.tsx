import { XIcon } from 'lucide-react'
import { useEffect, useRef } from 'react'

import { Button } from '@/components/ui/button'
import type { Entry } from '@/interview/state'
import { cn } from '@/lib/utils'
import { T } from '@/settings/translated-text'
import { localise } from '@/settings/i18n'

/** The whole conversation, as chat bubbles, in a side panel. */
export function TranscriptPanel({ entries, onClose }: { entries: Entry[]; onClose?: () => void }) {
  const bottom = useRef<HTMLDivElement>(null)
  useEffect(() => {
    bottom.current?.scrollIntoView({ block: 'end', behavior: 'smooth' })
  }, [entries])
  return (
    <aside className="flex min-h-0 w-full flex-col rounded-2xl bg-zinc-900 ring-1 ring-white/5 md:w-96">
      <div className="flex items-center justify-between border-b border-white/5 px-4 py-3">
        <h2 className="text-sm font-medium text-zinc-100">
          <T text={'Transcript'} />
        </h2>
        {onClose && (
          <Button
            size="icon-sm"
            variant="ghost"
            onClick={onClose}
            aria-label={localise('Close the transcript')}
          >
            <XIcon />
          </Button>
        )}
      </div>
      <div
        className="flex min-h-0 flex-1 flex-col gap-3 overflow-y-auto p-4"
        data-testid="transcript"
      >
        {entries.length === 0 && (
          <p className="text-sm text-zinc-500">
            <T text={'The conversation will appear here.'} />
          </p>
        )}
        {entries.map((entry) => {
          const mine = entry.speaker === 'candidate'
          return (
            <div
              key={`${entry.speaker}-${entry.turnSeq}`}
              className={cn(
                'flex max-w-[85%] flex-col gap-1',
                mine ? 'self-end items-end' : 'self-start',
              )}
            >
              <span className="text-[11px] text-zinc-500">
                <T text={mine ? 'You' : 'Interviewer'} />
                {entry.incomplete && ' · partly not transcribed'}
              </span>
              <div
                className={cn(
                  'rounded-2xl px-3 py-2 text-sm leading-relaxed',
                  mine
                    ? 'rounded-br-md bg-emerald-600/90 text-white'
                    : 'rounded-bl-md bg-zinc-800 text-zinc-100',
                  !entry.final && 'opacity-70 italic',
                )}
              >
                {entry.text || '…'}
              </div>
            </div>
          )
        })}
        <div ref={bottom} />
      </div>
    </aside>
  )
}
