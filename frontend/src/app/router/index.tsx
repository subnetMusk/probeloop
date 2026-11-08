import { createRootRoute, createRoute, createRouter } from '@tanstack/react-router'

import { Root } from './root'
import { InterviewPage } from '@/pages/live-interview'
import { SessionPage } from '@/legacy/pages/session-page'
import { SessionsPage } from '@/legacy/pages/sessions-page'
import { SetupPage } from '@/legacy/setup/setup-page'
import { ReportPage } from '@/legacy/pages/report-page'
import { SettingsPage } from '@/pages/settings'

const rootRoute = createRootRoute({ component: Root })
const setupRoute = createRoute({ getParentRoute: () => rootRoute, path: '/', component: SetupPage })
const interviewRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/interview/$sessionId',
  component: InterviewPage,
})

const sessionsRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/sessions',
  component: SessionsPage,
})
const sessionRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/sessions/$sessionId',
  component: SessionPage,
})

const reportRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/reports/$reportId',
  component: ReportPage,
})

const settingsRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/settings',
  component: SettingsPage,
})

export const router = createRouter({
  routeTree: rootRoute.addChildren([
    setupRoute,
    interviewRoute,
    sessionsRoute,
    sessionRoute,
    reportRoute,
    settingsRoute,
  ]),
})

declare module '@tanstack/react-router' {
  interface Register {
    router: typeof router
  }
}
