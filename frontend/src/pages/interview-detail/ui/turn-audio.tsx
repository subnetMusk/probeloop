import { PauseIcon, PlayIcon } from 'lucide-react'
import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import type { ReactNode } from 'react'

import { useMessages } from '@/shared/i18n'
import { clock } from '@/shared/lib/format'
import { Button } from '@/shared/ui/button'
import { transcriptMessages } from './messages'
import { TurnAudioContext, useTurnAudio } from './turn-audio-context'
import type { Playback, TurnAudio } from './turn-audio-context'

/**
 * One player for every turn of a transcript, so starting a turn stops the one that was playing.
 * The audio element is created on first use and released with the page.
 */
export function TurnAudioProvider({ children }: { children: ReactNode }) {
  const audio = useRef<HTMLAudioElement | null>(null)
  const stopAt = useRef<number | null>(null)
  const [playback, setPlayback] = useState<Playback | null>(null)

  const element = useCallback(() => {
    if (audio.current) return audio.current
    const el = new Audio()
    el.preload = 'none'
    const sync = () => {
      if (stopAt.current !== null && el.currentTime >= stopAt.current) {
        stopAt.current = null
        el.pause()
      }
      setPlayback((previous) =>
        previous
          ? {
              ...previous,
              playing: !el.paused && !el.ended,
              current: el.currentTime,
              duration: Number.isFinite(el.duration) ? el.duration : previous.duration,
            }
          : previous,
      )
    }
    for (const event of ['play', 'pause', 'ended', 'timeupdate', 'loadedmetadata']) {
      el.addEventListener(event, sync)
    }
    audio.current = el
    return el
  }, [])

  useEffect(
    () => () => {
      audio.current?.pause()
      audio.current = null
    },
    [],
  )

  const start = useCallback(
    (src: string, from?: number) => {
      const el = element()
      const same = playback?.src === src
      if (!same) {
        el.src = src
        setPlayback({ src, playing: true, current: 0, duration: 0 })
      }
      if (from !== undefined) el.currentTime = Math.max(0, from)
      el.play().catch(() => {
        setPlayback((previous) => (previous ? { ...previous, playing: false } : previous))
      })
    },
    [element, playback?.src],
  )

  const value = useMemo<TurnAudio>(
    () => ({
      playback,
      toggle: (src) => {
        stopAt.current = null
        if (playback?.src === src && playback.playing) element().pause()
        else start(src)
      },
      playRange: (src, from, to) => {
        stopAt.current = to
        start(src, from)
      },
      stop: () => {
        stopAt.current = null
        audio.current?.pause()
      },
    }),
    [playback, element, start],
  )
  return <TurnAudioContext value={value}>{children}</TurnAudioContext>
}

/** Play/pause for one turn, with its position while it is the turn being played. */
export function TurnAudioButton({ src, label }: { src: string; label: string }) {
  const t = useMessages(transcriptMessages)
  const player = useTurnAudio()
  if (!player) return null
  const active = player.playback?.src === src ? player.playback : null
  const playing = active?.playing === true
  return (
    <span className="inline-flex items-center gap-2">
      <Button
        type="button"
        size="sm"
        variant="ghost"
        aria-label={playing ? t.pause(label) : t.listen(label)}
        aria-pressed={playing}
        onClick={() => {
          player.toggle(src)
        }}
      >
        {playing ? <PauseIcon data-icon="inline-start" /> : <PlayIcon data-icon="inline-start" />}
        {playing ? t.pauseShort : t.listenShort}
      </Button>
      {active && active.duration > 0 && (
        <span className="text-xs text-muted-foreground tabular-nums" aria-hidden="true">
          {clock(active.current)} / {clock(active.duration)}
        </span>
      )}
    </span>
  )
}
