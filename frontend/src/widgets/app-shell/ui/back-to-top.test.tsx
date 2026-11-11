// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, expect, it, vi } from 'vitest'

import { setLanguage } from '@/shared/lib/preferences'
import { BackToTop } from './back-to-top'

afterEach(() => {
  cleanup()
  document.body.replaceChildren()
  vi.unstubAllGlobals()
})

it.each([false, true])(
  'returns keyboard focus to the heading with reduced motion set to %s',
  (reducedMotion) => {
    setLanguage('it')
    vi.stubGlobal('matchMedia', () => ({ matches: reducedMotion }))
    const content = document.createElement('div')
    const heading = document.createElement('h1')
    heading.textContent = 'Guide'
    content.append(heading)
    document.body.append(content)
    Object.defineProperties(content, {
      scrollHeight: { value: 4000 },
      clientHeight: { value: 600 },
      scrollTop: { value: 3400 },
    })
    const scrollTo = vi.fn()
    content.scrollTo = scrollTo

    render(<BackToTop target={{ current: content }} />)
    const button = screen.getByRole('button', { name: 'Torna su' })
    expect(button.textContent).toBe('')
    button.focus()
    fireEvent.click(button)

    expect(scrollTo).toHaveBeenCalledWith({
      top: 0,
      behavior: reducedMotion ? 'auto' : 'smooth',
    })
    expect(document.activeElement).toBe(heading)
  },
)
