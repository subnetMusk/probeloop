import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import type { ReactNode } from 'react'

import { AudioStateContext } from './audio-state'
import type { AudioKit, AudioState } from './audio-state'
import { Microphone, MicrophoneError } from './microphone'
import { SpeechPlayer } from './player'

/**
 * One AudioContext, microphone and player for the whole app, so the microphone checked on the
 * setup page is the one the interview uses.
 */
export function AudioProvider({ children }: { children: ReactNode }) {
  const [kit, setKit] = useState<AudioKit | null>(null)
  const [level, setLevel] = useState(-Infinity)
  const [problem, setProblem] = useState<AudioState['problem']>(null)
  const [enabling, setEnabling] = useState(false)
  const contextRef = useRef<AudioContext | null>(null)

  const enable = useCallback(async () => {
    setEnabling(true)
    setProblem(null)
    try {
      contextRef.current ??= new AudioContext({ latencyHint: 'interactive' })
      const context = contextRef.current
      await context.resume()
      const microphone = await Microphone.open(context)
      microphone.onLevel = setLevel
      microphone.onLost = () => {
        setProblem('lost')
        setKit(null)
      }
      setKit({ context, microphone, player: new SpeechPlayer(context) })
    } catch (error) {
      setProblem(error instanceof MicrophoneError ? error.problem : 'failed')
    } finally {
      setEnabling(false)
    }
  }, [])

  useEffect(
    () => () => {
      kit?.microphone.close()
    },
    [kit],
  )

  const value = useMemo(
    () => ({ kit, level, problem, enabling, enable }),
    [kit, level, problem, enabling, enable],
  )
  return <AudioStateContext.Provider value={value}>{children}</AudioStateContext.Provider>
}
