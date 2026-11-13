import { Outlet, useMatches, useRouterState } from '@tanstack/react-router'
import { useEffect, useRef } from 'react'

import { useMessages } from '@/shared/i18n'
import { TooltipProvider } from '@/shared/ui/tooltip'
import { pageSlug, tabTitle } from '../model/crumbs'
import { BackToTop } from './back-to-top'
import { Breadcrumbs } from './breadcrumbs'
import { Footer } from './footer'
import { shellMessages } from './messages'
import { Header } from './navigation'
import { ReportNotifications } from './report-notifications'

/**
 * The app shell: header, breadcrumbs, page and footer. The header stays in place and only the
 * area below it scrolls, so the scroll bar never runs beside the navigation. Routes marked
 * `chrome: 'none'` (the interview call, full screen like a video call) get the page alone;
 * routes marked `chrome: 'workspace'` (the transcript review) get the header and the whole
 * window below it, without the footer.
 */
export function Layout() {
  const t = useMessages(shellMessages)
  const pages: Record<string, string> = t.pages
  const matches = useMatches()
  const chromeless = matches.some((match) => match.staticData.chrome === 'none')
  const workspace = matches.some((match) => match.staticData.chrome === 'workspace')
  const notFound = matches.some((match) => match.status === 'notFound' || match._notFound === true)
  const slug = pageSlug(matches)
  const pathname = useRouterState({ select: (state) => state.location.pathname })
  const content = useRef<HTMLDivElement>(null)
  useEffect(() => {
    // A not-found boundary names the tab even when an ancestor route still matches.
    if (slug && !notFound) document.title = tabTitle(pages[slug] ?? slug)
  }, [slug, pages, notFound])
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
  if (workspace)
    // Wide windows give the page the whole area below the header and the page scrolls its own
    // panes; narrow ones scroll the area as a whole, like any other page.
    return (
      <TooltipProvider delayDuration={300}>
        <div className="flex h-svh flex-col overflow-hidden bg-background text-foreground">
          <Header />
          <div
            ref={content}
            data-testid="content"
            className="flex min-h-0 flex-1 flex-col overflow-y-auto lg:overflow-hidden"
          >
            <div className="w-full px-4 pt-4 lg:px-6">
              <Breadcrumbs />
            </div>
            <div className="flex min-h-0 flex-1 flex-col">
              <Outlet />
            </div>
            <ReportNotifications />
          </div>
        </div>
      </TooltipProvider>
    )
  return (
    <TooltipProvider delayDuration={300}>
      <div className="flex h-svh flex-col overflow-hidden bg-background text-foreground">
        <Header />
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
          <BackToTop target={content} />
          <ReportNotifications />
          <Footer />
        </div>
      </div>
    </TooltipProvider>
  )
}
