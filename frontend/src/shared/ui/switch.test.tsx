// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'

import { Switch } from './switch'

beforeEach(() => {
  vi.stubGlobal(
    'ResizeObserver',
    class {
      observe = vi.fn()
      unobserve = vi.fn()
      disconnect = vi.fn()
    },
  )
})

afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
})

it('submits the on/off value and supports its label and disabled state', () => {
  const { rerender } = render(
    <form aria-label="Installation">
      <label htmlFor="refinement">Second transcription</label>
      <Switch id="refinement" name="refinement" />
    </form>,
  )
  const form = screen.getByRole('form') as HTMLFormElement
  const control = screen.getByRole('switch', { name: 'Second transcription' })
  expect(new FormData(form).get('refinement')).toBeNull()
  fireEvent.click(control)
  expect(control.getAttribute('aria-checked')).toBe('true')
  expect(new FormData(form).get('refinement')).toBe('on')
  fireEvent.click(screen.getByText('Second transcription'))
  expect(control.getAttribute('aria-checked')).toBe('false')
  expect(new FormData(form).get('refinement')).toBeNull()
  rerender(
    <form aria-label="Installation">
      <label htmlFor="refinement">Second transcription</label>
      <Switch id="refinement" name="refinement" disabled />
    </form>,
  )
  fireEvent.click(control)
  expect(control.getAttribute('aria-checked')).toBe('false')
})
