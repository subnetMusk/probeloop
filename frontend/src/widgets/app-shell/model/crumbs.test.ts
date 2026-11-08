import { describe, expect, it } from 'vitest'

import { crumbsOf, pageSlug, tabTitle } from './crumbs'

const match = (pathname: string, slug?: string) => ({ pathname, staticData: { slug } })

describe('breadcrumbs', () => {
  it('starts from the dashboard and lists every route with a slug', () => {
    const matches = [
      match('/'),
      match('/interviews', 'interviews'),
      match('/interviews/abc', 'interview-detail'),
      match('/interviews/abc/', undefined),
    ]
    expect(crumbsOf(matches)).toEqual([
      { slug: 'dashboard', to: '/dashboard' },
      { slug: 'interviews', to: '/interviews' },
      { slug: 'interview-detail', to: '/interviews/abc' },
    ])
    expect(pageSlug(matches)).toBe('interview-detail')
  })

  it('does not repeat the dashboard', () => {
    expect(crumbsOf([match('/'), match('/dashboard', 'dashboard')])).toEqual([
      { slug: 'dashboard', to: '/dashboard' },
    ])
  })

  it('names the tab after the page slug', () => {
    expect(tabTitle('new-interview')).toBe('new-interview | ProbeLoop')
    expect(tabTitle(undefined)).toBe('ProbeLoop')
  })
})
