import { useQuery } from '@tanstack/react-query'

import { api } from '@/shared/api'
import { useAudio } from '@/shared/lib/audio'

export const speechStatusQuery = {
  queryKey: ['speech-status'],
  queryFn: api.speechStatus,
} as const

/** Whether a voice interview in `language` can start: microphone, speech services and voice. */
export function useVoiceReadiness(language: string) {
  const audio = useAudio()
  const speech = useQuery({
    ...speechStatusQuery,
    refetchInterval: (query) => (query.state.data?.ready ? false : 5000),
  })
  const voice = speech.data?.voices[language] ?? null
  return {
    audio,
    speech,
    voice,
    ready: audio.kit !== null && speech.data?.ready === true && voice !== null,
  }
}
