import { useEffect } from 'react'

import { useAudio } from '@/audio/audio-state'
import { usePreferences } from '@/settings/preferences'

export function PreferencesEffects() {
  const { language, theme, volume } = usePreferences()
  const { kit } = useAudio()
  useEffect(() => {
    document.documentElement.lang = language
    const media = window.matchMedia('(prefers-color-scheme: dark)')
    const update = () => {
      document.documentElement.classList.toggle(
        'dark',
        theme === 'dark' || (theme === 'system' && media.matches),
      )
    }
    update()
    media.addEventListener('change', update)
    return () => {
      media.removeEventListener('change', update)
    }
  }, [language, theme])
  useEffect(() => {
    kit?.player.setVolume(volume)
  }, [kit, volume])
  return null
}
