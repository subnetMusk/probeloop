import { Link, Outlet, useMatches, useRouterState } from '@tanstack/react-router'
import { useEffect, useRef } from 'react'

import { useMessages } from '@/shared/i18n'
import { TooltipProvider } from '@/shared/ui/tooltip'
import { Wordmark } from '@/shared/ui/wordmark'
import { pageSlug, tabTitle } from '../model/crumbs'
import { BackToTop } from './back-to-top'
import { Breadcrumbs } from './breadcrumbs'
import { Footer } from './footer'
import { shellMessages } from './messages'
import { ReportNotifications } from './report-notifications'

const NAV_LINK = 'rounded-md px-3 py-1.5 hover:bg-muted'
const NAV_ACTIVE = { className: 'font-medium text-foreground bg-muted' }

/**
 * The app shell: header, breadcrumbs, page and footer. The header stays in place and only the
 * area below it scrolls, so the scroll bar never runs beside the navigation. Routes marked
 * `chrome: 'none'` (the interview call, full screen like a video call) get the page alone.
 */
export function Layout() {
  const t = useMessages(shellMessages)
  const matches = useMatches()
  const chromeless = matches.some((match) => match.staticData.chrome === 'none')
  const slug = pageSlug(matches)
  const pathname = useRouterState({ select: (state) => state.location.pathname })
  const content = useRef<HTMLDivElement>(null)
  useEffect(() => {
    // Pages without a route slug (not found) name the tab themselves.
    if (slug) document.title = tabTitle(slug)
  }, [slug])
  useEffect(() => {
    // The router restores the window's scroll; the content area is scrolled here instead.
    content.current?.scrollTo({ top: 0 })
  }, [pathname])
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
      <div className="flex h-svh flex-col overflow-hidden bg-background text-foreground">
        <header className="z-20 shrink-0 border-b bg-background">
          <div className="mx-auto flex max-w-6xl flex-wrap items-center gap-2 px-6 py-3">
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
        <div
          ref={content}
          data-testid="content"
          className="flex flex-1 flex-col overflow-y-auto [scrollbar-gutter:stable]"
        >
          <div className="mx-auto w-full max-w-6xl px-6 pt-5">
            <Breadcrumbs />
          </div>
          <div className="flex-1">
            <Outlet />
          </div>
          <ReportNotifications />
          <Footer />
        </div>
        <BackToTop target={content} />
      </div>
    </TooltipProvider>
  )
}
