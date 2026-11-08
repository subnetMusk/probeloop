import { Link, Outlet, useRouterState } from '@tanstack/react-router'

import { TooltipProvider } from '@/components/ui/tooltip'
import { ReportNotifications } from '@/reports/report-notifications'
import { PreferencesEffects } from '@/settings/preferences-effects'
import { useLanguage } from '@/settings/preferences'
import { T } from '@/settings/translated-text'

/** The app shell. The interview is full screen, like a video call, so it has no header. */
export function Layout() {
  const it = useLanguage() === 'it'
  const inCall = useRouterState({ select: (s) => s.location.pathname.startsWith('/interview/') })
  return (
    <TooltipProvider delayDuration={300}>
      <PreferencesEffects />
      <div className="min-h-svh bg-background text-foreground">
        {!inCall && (
          <header className="border-b bg-background/80 backdrop-blur">
            <div className="mx-auto flex max-w-5xl items-center gap-2 px-6 py-3">
              <Link to="/" className="flex items-center gap-2">
                <span className="flex size-7 items-center justify-center rounded-lg bg-indigo-500 font-heading font-semibold text-white">
                  P
                </span>
                <span className="font-heading text-lg font-semibold">ProbeLoop</span>
              </Link>
              <span className="ml-2 hidden text-sm text-muted-foreground sm:inline">
                <T text={'interview practice, out loud'} />
              </span>
              <nav className="ml-auto flex items-center gap-1 text-sm">
                <Link
                  to="/"
                  className="rounded-md px-3 py-1.5 hover:bg-muted"
                  activeProps={{ className: 'font-medium text-foreground' }}
                  activeOptions={{ exact: true }}
                >
                  <T text={it ? 'Nuovo colloquio' : 'New interview'} />
                </Link>
                <Link
                  to="/sessions"
                  className="rounded-md px-3 py-1.5 hover:bg-muted"
                  activeProps={{ className: 'font-medium text-foreground' }}
                >
                  <T text={it ? 'I tuoi colloqui' : 'Your interviews'} />
                </Link>
              </nav>
              <Link to="/settings" className="rounded-md px-3 py-1.5 text-sm hover:bg-muted">
                {it ? 'Impostazioni' : 'Settings'}
              </Link>
            </div>
          </header>
        )}
        <Outlet />
        {!inCall && <ReportNotifications />}
      </div>
    </TooltipProvider>
  )
}
