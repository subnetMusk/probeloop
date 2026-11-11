// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'

import { TocLayout } from './page-toc'

let positions: Record<string, number>

beforeEach(() => {
  positions = { reader: 65, intro: 100, brief: 130, end: 150 }
  vi.spyOn(HTMLElement.prototype, 'getBoundingClientRect').mockImplementation(function (
    this: HTMLElement,
  ) {
    const top = positions[this.id] ?? 0
    return { top, bottom: this.hasAttribute('data-app-header') ? 65 : top + 20 } as DOMRect
  })
  vi.stubGlobal('matchMedia', () => ({ matches: true }))
  vi.stubGlobal('ResizeObserver', undefined)
})

afterEach(() => {
  cleanup()
  vi.restoreAllMocks()
  vi.unstubAllGlobals()
})

function page() {
  const scrollTo = vi.fn()
  render(
    <>
      <header data-app-header />
      <div id="reader" style={{ overflowY: 'auto' }}>
        <TocLayout
          label="Contents"
          items={[
            { id: 'intro', label: 'Introduction' },
            { id: 'brief', label: 'Brief section' },
            { id: 'end', label: 'Last section' },
          ]}
        >
          {['intro', 'brief', 'end'].map((id) => (
            <section key={id} id={id} style={{ scrollMarginTop: '24px' }}>
              <h2>{id}</h2>
            </section>
          ))}
        </TocLayout>
      </div>
    </>,
  )
  const reader = document.getElementById('reader')!
  reader.scrollTo = scrollTo
  return { reader, scrollTo }
}

function active() {
  return screen
    .getAllByRole('link')
    .find((link) => link.getAttribute('aria-current') === 'location')
}

it('uses the visible content top and section margin without skipping brief sections', () => {
  const { reader } = page()
  expect(active()?.textContent).toBe('Introduction')
  positions.brief = 89
  positions.end = 109
  fireEvent.scroll(reader)
  expect(active()?.textContent).toBe('Brief section')
  positions.end = 89
  fireEvent.scroll(reader)
  expect(active()?.textContent).toBe('Last section')
})

it('keeps a clicked short section current when scrolling is clamped at the page end', () => {
  const { reader, scrollTo } = page()
  const link = screen.getAllByRole('link', { name: 'Brief section' })[0]!
  fireEvent.click(link)
  expect(scrollTo).toHaveBeenCalledWith({ top: 41, behavior: 'auto' })
  fireEvent.scroll(reader)
  expect(active()?.textContent).toBe('Brief section')
  expect(document.activeElement?.id).toBe('brief')
  fireEvent.wheel(reader)
  fireEvent.scroll(reader)
  expect(active()?.textContent).toBe('Introduction')
})

it('does not jump to the last entry when all sections fit in the viewport', () => {
  const { reader } = page()
  Object.defineProperties(reader, {
    clientHeight: { value: 600 },
    scrollHeight: { value: 600 },
  })
  fireEvent.scroll(reader)
  expect(active()?.textContent).toBe('Introduction')
})

it('gives short trailing sections their own activation interval before the page ends', () => {
  const { reader } = page()
  Object.defineProperties(reader, {
    clientHeight: { value: 600 },
    scrollHeight: { value: 1600 },
  })
  const scroll = (value: number) => {
    reader.scrollTop = value
    positions.intro = 89 - value
    positions.brief = 89 + 1080 - value
    positions.end = 89 + 1120 - value
    fireEvent.scroll(reader)
  }
  scroll(960)
  expect(active()?.textContent).toBe('Introduction')
  scroll(980)
  expect(active()?.textContent).toBe('Brief section')
  scroll(1000)
  expect(active()?.textContent).toBe('Last section')
})

it('resumes tracking when another control scrolls away from a chosen section', () => {
  const { reader } = page()
  Object.defineProperties(reader, {
    clientHeight: { value: 600 },
    scrollHeight: { value: 1600 },
  })
  fireEvent.click(screen.getAllByRole('link', { name: 'Brief section' })[0]!)
  expect(active()?.textContent).toBe('Brief section')
  fireEvent(reader, new Event('scrollend'))
  expect(active()?.textContent).toBe('Introduction')
})
