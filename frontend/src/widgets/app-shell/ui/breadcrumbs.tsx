import { Link, useMatches } from '@tanstack/react-router'

import { useMessages } from '@/shared/i18n'
import { crumbsOf } from '../model/crumbs'
import { shellMessages } from './messages'

/** The trail of page names from the dashboard to the current page (ADR 0021). */
export function Breadcrumbs() {
  const t = useMessages(shellMessages)
  const pages: Record<string, string> = t.pages
  const crumbs = crumbsOf(useMatches())
  return (
    <nav aria-label={t.breadcrumbs} className="text-sm text-muted-foreground">
      <ol className="flex flex-wrap items-center gap-1.5">
        {crumbs.map((crumb, index) => {
          const last = index === crumbs.length - 1
          return (
            <li key={crumb.to} className="flex items-center gap-1.5">
              {index > 0 && <span aria-hidden="true">›</span>}
              {last ? (
                <span aria-current="page" className="font-medium text-foreground">
                  {pages[crumb.slug] ?? crumb.slug}
                </span>
              ) : (
                <Link
                  to={crumb.to}
                  // Only the last crumb is the current page.
                  activeOptions={{ exact: true }}
                  className="rounded-sm hover:text-foreground hover:underline"
                >
                  {pages[crumb.slug] ?? crumb.slug}
                </Link>
              )}
            </li>
          )
        })}
      </ol>
    </nav>
  )
}
