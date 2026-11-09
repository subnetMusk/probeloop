import { createContext, useContext } from 'react'
import { defineMessages } from '@/shared/i18n/messages'

import type { Microphone, MicrophoneProblem } from './microphone'
import type { SpeechPlayer } from './player'

export interface AudioKit {
  context: AudioContext
  microphone: Microphone
  player: SpeechPlayer
}

export interface AudioState {
  kit: AudioKit | null
  level: number // dBFS of the latest 100 ms of microphone audio
  problem: MicrophoneProblem | 'lost' | null
  enabling: boolean
  /** Must run from a click: browsers start audio only after a user gesture. */
  enable: () => Promise<void>
}

export const AudioStateContext = createContext<AudioState | null>(null)

export function useAudio(): AudioState {
  const state = useContext(AudioStateContext)
  if (!state) throw new Error('useAudio needs an AudioProvider')
  return state
}

export const audioMessages = defineMessages({
  en: {
    denied: 'Microphone access was denied. Allow it in the browser and try again.',
    not_found: 'No microphone was found. Connect one and try again.',
    unsupported:
      'This browser cannot capture audio here. Use a recent Chrome or Firefox on localhost.',
    failed: 'The microphone could not be opened.',
    lost: 'The microphone stopped (was it unplugged?). Enable it again.',
  },
  it: {
    denied: 'Accesso al microfono negato. Consentilo nel browser e riprova.',
    not_found: 'Nessun microfono trovato. Collegane uno e riprova.',
    unsupported:
      'Questo browser non può registrare qui. Usa una versione recente di Chrome o Firefox su localhost.',
    failed: 'Impossibile aprire il microfono.',
    lost: 'Il microfono si è fermato. Attivalo di nuovo.',
  },
})
