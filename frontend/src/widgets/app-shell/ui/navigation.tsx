import { Link } from '@tanstack/react-router'
import { MenuIcon, XIcon } from 'lucide-react'
import { Dialog as DialogPrimitive } from 'radix-ui'
import { useState } from 'react'

import { useMessages } from '@/shared/i18n'
import { cn } from '@/shared/lib/utils'
import { Wordmark } from '@/shared/ui/wordmark'
import { shellMessages } from './messages'
import { ThemeToggle } from './theme-toggle'

const NAV_ITEMS = [
  { to: '/dashboard', key: 'dashboard' },
  { to: '/new-interview', key: 'newInterview' },
  { to: '/interviews', key: 'interviews' },
  { to: '/cv-checks', key: 'cvChecks' },
  { to: '/profiles', key: 'profiles' },
  { to: '/guide', key: 'guide' },
  { to: '/settings', key: 'settings' },
] as const

/** The header row, shared by the page and the open mobile menu so the logo never moves. */
const ROW = 'relative mx-auto flex h-16 w-full max-w-6xl items-center gap-2 px-4 sm:px-6'
const ICON_BUTTON =
  'flex size-10 items-center justify-center rounded-full text-foreground outline-none transition-colors hover:bg-muted focus-visible:ring-3 focus-visible:ring-ring/50'

function Logo({ onNavigate }: { onNavigate?: () => void }) {
  return (
    <Link
      to="/dashboard"
      onClick={onNavigate}
      aria-label="ProbeLoop, dashboard"
      className="absolute left-1/2 -translate-x-1/2 rounded-md outline-none focus-visible:ring-3 focus-visible:ring-ring/50 lg:static lg:translate-x-0"
    >
      <Wordmark className="text-[1.7rem] leading-none" />
    </Link>
  )
}

/**
 * The application header. Wide windows show every destination; below `lg` a menu button opens
 * them full screen, while the logo stays centred in the same place in both states.
 */
export function Header() {
  const t = useMessages(shellMessages)
  return (
    <header data-app-header className="z-20 shrink-0 border-b bg-background">
      <div className={ROW}>
        <MobileMenu />
        <Logo />
        <nav aria-label={t.nav.label} className="ml-auto hidden items-center gap-1 lg:flex">
          {NAV_ITEMS.map((item) => (
            <Link
              key={item.to}
              to={item.to}
              className="rounded-md px-3 py-1.5 text-sm text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
              activeProps={{ className: 'bg-muted font-medium text-foreground' }}
            >
              {t.nav[item.key]}
            </Link>
          ))}
        </nav>
        <ThemeToggle className="ml-auto lg:ml-1" />
      </div>
    </header>
  )
}

function MobileMenu() {
  const t = useMessages(shellMessages)
  const [open, setOpen] = useState(false)
  return (
    <DialogPrimitive.Root open={open} onOpenChange={setOpen}>
      <DialogPrimitive.Trigger asChild>
        <button
          type="button"
          aria-label={t.menu.open}
          data-testid="menu-open"
          className={cn(ICON_BUTTON, 'lg:hidden')}
        >
          <MenuIcon className="size-6" aria-hidden />
        </button>
      </DialogPrimitive.Trigger>
      <DialogPrimitive.Portal>
        <DialogPrimitive.Content
          aria-describedby={undefined}
          className="fixed inset-0 z-50 flex flex-col bg-background text-foreground outline-none data-[state=open]:animate-in data-[state=open]:fade-in-0 data-[state=closed]:animate-out data-[state=closed]:fade-out-0 motion-reduce:animate-none"
        >
          <DialogPrimitive.Title className="sr-only">{t.menu.title}</DialogPrimitive.Title>
          <div className="border-b">
            <div className={ROW}>
              <DialogPrimitive.Close asChild>
                <button type="button" aria-label={t.menu.close} className={ICON_BUTTON}>
                  <XIcon className="size-6" aria-hidden />
                </button>
              </DialogPrimitive.Close>
              <Logo
                onNavigate={() => {
                  setOpen(false)
                }}
              />
              <ThemeToggle className="ml-auto" />
            </div>
          </div>
          <nav aria-label={t.nav.label} className="flex-1 overflow-y-auto px-4 py-6 sm:px-6">
            <ul className="mx-auto flex max-w-md flex-col gap-1">
              {NAV_ITEMS.map((item, index) => (
                <li
                  key={item.to}
                  className="motion-safe:animate-in motion-safe:fade-in-0 motion-safe:slide-in-from-bottom-2"
                  style={{ animationDelay: `${String(index * 30)}ms`, animationFillMode: 'both' }}
                >
                  <Link
                    to={item.to}
                    onClick={() => {
                      setOpen(false) // the chosen page replaces the menu
                    }}
                    className="flex items-center rounded-xl px-4 py-3.5 font-heading text-xl font-medium text-foreground/80 transition-colors hover:bg-muted hover:text-foreground"
                    activeProps={{ className: 'bg-muted text-foreground' }}
                  >
                    {t.nav[item.key]}
                  </Link>
                </li>
              ))}
            </ul>
          </nav>
        </DialogPrimitive.Content>
      </DialogPrimitive.Portal>
    </DialogPrimitive.Root>
  )
}
