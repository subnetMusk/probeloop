import { Link, Outlet, useRouterState } from '@tanstack/react-router'

import { TooltipProvider } from '@/components/ui/tooltip'

/** The app shell. The interview is full screen, like a video call, so it has no header. */
export function Layout() {
  const inCall = useRouterState({ select: (s) => s.location.pathname.startsWith('/interview/') })
  return (
    <TooltipProvider delayDuration={300}>
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
                interview practice, out loud
              </span>
            </div>
          </header>
        )}
        <Outlet />
      </div>
    </TooltipProvider>
  )
}
