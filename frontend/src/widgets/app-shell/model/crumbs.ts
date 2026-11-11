/** What the shell needs from a matched route. */
export interface RouteMatchLike {
  pathname: string
  staticData: { slug?: string; chrome?: 'none' }
}

export interface Crumb {
  slug: string
  to: string
}

export const HOME: Crumb = { slug: 'dashboard', to: '/dashboard' }

/**
 * The breadcrumb trail: every matched route that declares a slug, starting from the dashboard.
 * Index routes share their parent's path and declare no slug, so each path appears once.
 */
export function crumbsOf(matches: readonly RouteMatchLike[]): Crumb[] {
  const crumbs = matches
    .filter((match) => match.staticData.slug)
    .map((match) => ({ slug: match.staticData.slug ?? '', to: match.pathname.replace(/\/$/, '') }))
  return crumbs[0]?.slug === HOME.slug ? crumbs : [HOME, ...crumbs]
}

/** The slug of the deepest matched route, which names the page. */
export function pageSlug(matches: readonly RouteMatchLike[]): string | undefined {
  return [...matches].reverse().find((match) => match.staticData.slug)?.staticData.slug
}

/** The browser tab title: `<page name> | ProbeLoop`. */
export function tabTitle(name: string | undefined): string {
  return name ? `${name} | ProbeLoop` : 'ProbeLoop'
}
