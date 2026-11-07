import { createRootRoute, createRoute, createRouter } from '@tanstack/react-router'

import { Layout } from '@/components/layout'
import { InterviewPage } from '@/pages/interview-page'
import { SetupPage } from '@/pages/setup-page'

const rootRoute = createRootRoute({ component: Layout })
const setupRoute = createRoute({ getParentRoute: () => rootRoute, path: '/', component: SetupPage })
const interviewRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/interview/$sessionId',
  component: InterviewPage,
})

export const router = createRouter({
  routeTree: rootRoute.addChildren([setupRoute, interviewRoute]),
})

declare module '@tanstack/react-router' {
  interface Register {
    router: typeof router
  }
}
