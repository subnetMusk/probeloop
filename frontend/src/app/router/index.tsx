/* eslint-disable @typescript-eslint/only-throw-error -- TanStack Router redirects are thrown objects. */
import {
  Outlet,
  createRootRoute,
  createRoute,
  createRouter,
  redirect,
} from '@tanstack/react-router'

import { SessionPage } from '@/legacy/pages/session-page'
import { SessionsPage } from '@/legacy/pages/sessions-page'
import { ReportPage } from '@/legacy/pages/report-page'
import { SetupPage } from '@/legacy/setup/setup-page'
import { AccessibilityPage } from '@/pages/accessibility'
import { InterviewPage } from '@/pages/live-interview'
import { NotFoundPage } from '@/pages/not-found'
import { SettingsPage } from '@/pages/settings'
import { api } from '@/shared/api'
import { Root } from './root'

// Every route that names a page declares its slug: the URL segment, the breadcrumb label and the
// tab title (`<slug> | ProbeLoop`) are the same, in English (ADR 0014). Detail pages of a user's
// resources use a generic slug and keep the resource id in the URL.
declare module '@tanstack/react-router' {
  interface StaticDataRouteOption {
    slug?: string
    /** `none` hides the app shell, for the full-screen interview call. */
    chrome?: 'none'
  }
}

const rootRoute = createRootRoute({ component: Root, notFoundComponent: NotFoundPage })

const indexRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/',
  beforeLoad: () => {
    throw redirect({ to: '/dashboard', replace: true })
  },
})

// Until the dashboard of the redesign exists, it shows the interview history.
const dashboardRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: 'dashboard',
  staticData: { slug: 'dashboard' },
  component: SessionsPage,
})

const newInterviewRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: 'new-interview',
  staticData: { slug: 'new-interview' },
  component: SetupPage,
})

const liveInterviewRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: 'live-interview/$sessionId',
  staticData: { slug: 'live-interview', chrome: 'none' },
  component: InterviewPage,
})

const interviewsRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: 'interviews',
  staticData: { slug: 'interviews' },
  component: Outlet,
})
const interviewsIndexRoute = createRoute({
  getParentRoute: () => interviewsRoute,
  path: '/',
  component: SessionsPage,
})
const interviewRoute = createRoute({
  getParentRoute: () => interviewsRoute,
  path: '$sessionId',
  staticData: { slug: 'interview-detail' },
  component: Outlet,
})
const interviewIndexRoute = createRoute({
  getParentRoute: () => interviewRoute,
  path: '/',
  component: SessionPage,
})
const interviewReportRoute = createRoute({
  getParentRoute: () => interviewRoute,
  path: 'reports/$reportId',
  staticData: { slug: 'interview-report' },
  component: ReportPage,
})

// The CV check list and detail pages come with the dashboard; until then they lead there.
const toDashboard = () => {
  throw redirect({ to: '/dashboard', replace: true })
}
const cvChecksRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: 'cv-checks',
  staticData: { slug: 'cv-checks' },
  component: Outlet,
})
const cvChecksIndexRoute = createRoute({
  getParentRoute: () => cvChecksRoute,
  path: '/',
  beforeLoad: toDashboard,
})
const cvCheckRoute = createRoute({
  getParentRoute: () => cvChecksRoute,
  path: '$snapshotId',
  staticData: { slug: 'cv-check-detail' },
  component: Outlet,
})
const cvCheckIndexRoute = createRoute({
  getParentRoute: () => cvCheckRoute,
  path: '/',
  beforeLoad: toDashboard,
})
const cvReportRoute = createRoute({
  getParentRoute: () => cvCheckRoute,
  path: 'reports/$reportId',
  staticData: { slug: 'cv-report' },
  component: ReportPage,
})

const settingsRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: 'settings',
  staticData: { slug: 'settings' },
  component: SettingsPage,
})
const accessibilityRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: 'accessibility',
  staticData: { slug: 'accessibility' },
  component: AccessibilityPage,
})

// Earlier addresses, kept for bookmarks and for links stored by report notifications.
const oldSessionsRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: 'sessions',
  beforeLoad: () => {
    throw redirect({ to: '/interviews', replace: true })
  },
})
const oldSessionRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: 'sessions/$sessionId',
  beforeLoad: ({ params }) => {
    throw redirect({ to: '/interviews/$sessionId', params, replace: true })
  },
})
const oldCallRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: 'interview/$sessionId',
  beforeLoad: ({ params }) => {
    throw redirect({ to: '/live-interview/$sessionId', params, replace: true })
  },
})
const reportRedirectRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: 'reports/$reportId',
  beforeLoad: async ({ params }) => {
    const report = await api.report(params.reportId)
    if (report.kind === 'cv' && report.snapshot_id)
      throw redirect({
        to: '/cv-checks/$snapshotId/reports/$reportId',
        params: { snapshotId: report.snapshot_id, reportId: report.id },
        replace: true,
      })
    throw redirect({
      to: '/interviews/$sessionId/reports/$reportId',
      params: { sessionId: report.session_id ?? report.subject_id, reportId: report.id },
      replace: true,
    })
  },
})

export const router = createRouter({
  routeTree: rootRoute.addChildren([
    indexRoute,
    dashboardRoute,
    newInterviewRoute,
    liveInterviewRoute,
    interviewsRoute.addChildren([
      interviewsIndexRoute,
      interviewRoute.addChildren([interviewIndexRoute, interviewReportRoute]),
    ]),
    cvChecksRoute.addChildren([
      cvChecksIndexRoute,
      cvCheckRoute.addChildren([cvCheckIndexRoute, cvReportRoute]),
    ]),
    settingsRoute,
    accessibilityRoute,
    oldSessionsRoute,
    oldSessionRoute,
    oldCallRoute,
    reportRedirectRoute,
  ]),
})

declare module '@tanstack/react-router' {
  interface Register {
    router: typeof router
  }
}
