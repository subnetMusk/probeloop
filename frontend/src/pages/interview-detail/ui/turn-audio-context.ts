import { createContext, use } from 'react'

export interface Playback {
  src: string
  playing: boolean
  current: number
  duration: number
}

export interface TurnAudio {
  playback: Playback | null
  /** Plays a turn from where it stopped, or pauses it if it is playing. */
  toggle: (src: string) => void
  /** Plays a stretch of a turn, for example around a doubtful word. */
  playRange: (src: string, from: number, to: number) => void
  stop: () => void
}

export const TurnAudioContext = createContext<TurnAudio | null>(null)

/** The transcript's shared player, or `null` outside a `TurnAudioProvider`. */
export function useTurnAudio(): TurnAudio | null {
  return use(TurnAudioContext)
}
