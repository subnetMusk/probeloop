import { Link, Outlet, useMatches } from '@tanstack/react-router'
import { useEffect } from 'react'

import { useMessages } from '@/shared/i18n'
import { TooltipProvider } from '@/shared/ui/tooltip'
import { Wordmark } from '@/shared/ui/wordmark'
import { pageSlug, tabTitle } from '../model/crumbs'
import { Breadcrumbs } from './breadcrumbs'
import { Footer } from './footer'
import { shellMessages } from './messages'
import { ReportNotifications } from './report-notifications'

const NAV_LINK = 'rounded-md px-3 py-1.5 hover:bg-muted'
const NAV_ACTIVE = { className: 'font-medium text-foreground bg-muted' }

/**
 * The app shell: header, breadcrumbs, page and footer. Routes marked `chrome: 'none'` (the
 * interview call, full screen like a video call) get the page alone.
 */
export function Layout() {
  const t = useMessages(shellMessages)
  const matches = useMatches()
  const chromeless = matches.some((match) => match.staticData.chrome === 'none')
  const slug = pageSlug(matches)
  useEffect(() => {
    // Pages without a route slug (not found) name the tab themselves.
    if (slug) document.title = tabTitle(slug)
  }, [slug])
  if (chromeless)
    return (
      <TooltipProvider delayDuration={300}>
        <div className="min-h-svh bg-background text-foreground">
          <Outlet />
        </div>
      </TooltipProvider>
    )
  return (
    <TooltipProvider delayDuration={300}>
      <div className="flex min-h-svh flex-col bg-background text-foreground">
        <header className="border-b bg-background/80 backdrop-blur">
          <div className="mx-auto flex max-w-5xl flex-wrap items-center gap-2 px-6 py-3">
            <Link to="/dashboard" aria-label="ProbeLoop, dashboard">
              <Wordmark />
            </Link>
            <nav
              aria-label={t.nav.label}
              className="ml-auto flex flex-wrap items-center gap-1 text-sm"
            >
              <Link to="/dashboard" className={NAV_LINK} activeProps={NAV_ACTIVE}>
                {t.nav.dashboard}
              </Link>
              <Link to="/new-interview" className={NAV_LINK} activeProps={NAV_ACTIVE}>
                {t.nav.newInterview}
              </Link>
              <Link to="/interviews" className={NAV_LINK} activeProps={NAV_ACTIVE}>
                {t.nav.interviews}
              </Link>
              <Link to="/cv-checks" className={NAV_LINK} activeProps={NAV_ACTIVE}>
                {t.nav.cvChecks}
              </Link>
              <Link to="/profiles" className={NAV_LINK} activeProps={NAV_ACTIVE}>
                {t.nav.profiles}
              </Link>
              <Link to="/settings" className={NAV_LINK} activeProps={NAV_ACTIVE}>
                {t.nav.settings}
              </Link>
            </nav>
          </div>
        </header>
        <div className="mx-auto w-full max-w-5xl px-6 pt-4">
          <Breadcrumbs />
        </div>
        <div className="flex-1">
          <Outlet />
        </div>
        <ReportNotifications />
        <Footer />
      </div>
    </TooltipProvider>
  )
}
