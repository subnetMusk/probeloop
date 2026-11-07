import { createRootRoute, createRoute, createRouter } from '@tanstack/react-router'

import { Layout } from '@/components/layout'
import { InterviewPage } from '@/pages/interview-page'
import { SessionPage } from '@/pages/session-page'
import { SessionsPage } from '@/pages/sessions-page'
import { SetupPage } from '@/pages/setup-page'

const rootRoute = createRootRoute({ component: Layout })
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

export const router = createRouter({
  routeTree: rootRoute.addChildren([setupRoute, interviewRoute, sessionsRoute, sessionRoute]),
})

declare module '@tanstack/react-router' {
  interface Register {
    router: typeof router
  }
}
