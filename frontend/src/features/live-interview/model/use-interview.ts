import { useCallback, useEffect, useReducer, useRef } from 'react'

import { SessionSocket } from '@/shared/api'
import type { AudioKit } from '@/shared/lib/audio'

import { initialState, reduce } from './state'

const BUSY = 4409 // the server still holds a previous connection of this page
const MAX_BUSY_RETRIES = 10

/**
 * Connects the page to a live session and wires the audio: microphone frames go out while the
 * candidate answers, the interviewer's sentences are scheduled as they arrive, and the server is
 * told when playback has finished. Starting the interview happens as soon as the session is
 * ready: the server then loads its resources and reports progress.
 */
export function useInterview(sessionId: string, kit: AudioKit | null) {
  const [state, dispatch] = useReducer(reduce, initialState)
  const socketRef = useRef<SessionSocket | null>(null)
  const requestedStart = useRef(false)

  useEffect(() => {
    if (!kit) return
    const { microphone, player } = kit
    let busyRetries = 0
    let retry: ReturnType<typeof setTimeout> | undefined
    let disposed = false

    const socket = new SessionSocket(sessionId, (event) => {
      switch (event.kind) {
        case 'open':
          dispatch({ type: 'connection', connection: 'open' })
          break
        case 'closed':
          microphone.forwardFrames(null)
          player.stop()
          if (!disposed && event.code === BUSY && busyRetries++ < MAX_BUSY_RETRIES) {
            retry = setTimeout(() => {
              socket.connect()
            }, 300)
          } else {
            dispatch({ type: 'connection', connection: 'closed' })
          }
          break
        case 'audio':
          player.enqueue(event.pcm, event.chunk.sample_rate)
          break
        case 'message': {
          const message = event.message
          dispatch({ type: 'server', message, at: performance.now() })
          if (message.type === 'state.changed') {
            if (message.status === 'ready' && !requestedStart.current) {
              requestedStart.current = true
              player.begin(() => undefined)
              socket.command('session.start')
            }
            if (message.status !== 'in_progress' || message.phase !== 'candidate_speaking') {
              microphone.forwardFrames(null)
            }
            if (message.status !== 'in_progress') player.stop()
          } else if (message.type === 'tts.done') {
            player.finish(() => {
              socket.command('playback.finished')
            })
          }
          break
        }
      }
    })
    socket.connect()
    socketRef.current = socket
    return () => {
      disposed = true
      clearTimeout(retry)
      microphone.forwardFrames(null)
      player.stop()
      socket.close()
      socketRef.current = null
      requestedStart.current = false
    }
  }, [sessionId, kit])

  const answer = useCallback(() => {
    if (!kit) return
    const socket = socketRef.current
    if (!socket) return
    socket.command('turn.start')
    kit.microphone.forwardFrames((pcm) => {
      socket.sendAudio(pcm)
    })
  }, [kit])

  const endAnswer = useCallback(() => {
    if (!kit) return
    kit.microphone.forwardFrames(null)
    const endedAt = performance.now()
    kit.player.begin((startsAt) => {
      dispatch({ type: 'latency', ms: startsAt - endedAt })
    })
    socketRef.current?.endAnswer()
  }, [kit])

  const endCall = useCallback(() => {
    if (kit) {
      kit.microphone.forwardFrames(null)
      kit.player.stop()
    }
    socketRef.current?.command('session.end')
  }, [kit])

  const resume = useCallback(() => {
    kit?.player.begin(() => undefined)
    socketRef.current?.command('session.resume')
  }, [kit])

  const retryStart = useCallback(() => {
    dispatch({ type: 'notice', text: null })
    socketRef.current?.command('session.start')
  }, [])

  const dismissNotice = useCallback(() => {
    dispatch({ type: 'notice', text: null })
  }, [])

  return { state, answer, endAnswer, endCall, resume, retryStart, dismissNotice }
}
