import { useEffect } from 'react'

/** Run `action` when `key` is pressed outside text fields and buttons (which use it themselves). */
export function useHotkey(key: string, action: () => void, enabled: boolean): void {
  useEffect(() => {
    if (!enabled) return
    const onKey = (event: KeyboardEvent) => {
      if (event.key !== key || event.repeat || event.ctrlKey || event.metaKey || event.altKey)
        return
      const target = event.target as HTMLElement | null
      if (target?.closest('input, textarea, select, button, [contenteditable="true"]')) return
      event.preventDefault()
      action()
    }
    window.addEventListener('keydown', onKey)
    return () => {
      window.removeEventListener('keydown', onKey)
    }
  }, [key, action, enabled])
}
