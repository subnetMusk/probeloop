import { MoonIcon, SunIcon } from 'lucide-react'

import { useMessages } from '@/shared/i18n'
import { setTheme, useResolvedTheme } from '@/shared/lib/preferences'
import { cn } from '@/shared/lib/utils'
import { Tooltip, TooltipContent, TooltipTrigger } from '@/shared/ui/tooltip'
import { shellMessages } from './messages'

/**
 * Switches between the light and the dark theme in one click. The sun shows in the light theme
 * and the moon in the dark one; "follow the system" stays available in Settings.
 */
export function ThemeToggle({ className }: { className?: string }) {
  const t = useMessages(shellMessages)
  const dark = useResolvedTheme() === 'dark'
  const label = dark ? t.theme.toLight : t.theme.toDark
  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <button
          type="button"
          aria-label={label}
          data-testid="theme-toggle"
          onClick={() => {
            setTheme(dark ? 'light' : 'dark')
          }}
          className={cn(
            'relative flex size-10 items-center justify-center rounded-full text-muted-foreground outline-none transition-colors hover:bg-muted hover:text-foreground focus-visible:ring-3 focus-visible:ring-ring/50',
            className,
          )}
        >
          <SunIcon
            aria-hidden
            className={cn(
              'size-5 transition-all duration-300 motion-reduce:transition-none',
              dark ? 'scale-0 -rotate-90 opacity-0' : 'scale-100 rotate-0 opacity-100',
            )}
          />
          <MoonIcon
            aria-hidden
            className={cn(
              'absolute size-5 transition-all duration-300 motion-reduce:transition-none',
              dark ? 'scale-100 rotate-0 opacity-100' : 'scale-0 rotate-90 opacity-0',
            )}
          />
        </button>
      </TooltipTrigger>
      <TooltipContent>{label}</TooltipContent>
    </Tooltip>
  )
}
