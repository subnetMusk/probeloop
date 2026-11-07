import { Link, Outlet } from '@tanstack/react-router'

export function Layout() {
  return (
    <div className="min-h-svh bg-background text-foreground">
      <header className="border-b px-6 py-3">
        <Link to="/" className="font-heading text-lg font-semibold">
          ProbeLoop
        </Link>
      </header>
      <main>
        <Outlet />
      </main>
    </div>
  )
}
