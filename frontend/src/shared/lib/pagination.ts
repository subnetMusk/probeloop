import { useState } from 'react'

export interface Page<T> {
  items: T[]
  /** Zero-based, kept within range when the list shrinks. */
  page: number
  pages: number
  total: number
}

/** One page of `items`; an empty list has one empty page. */
export function pageOf<T>(items: readonly T[], page: number, size: number): Page<T> {
  const pages = Math.max(1, Math.ceil(items.length / size))
  const current = Math.min(Math.max(0, page), pages - 1)
  return {
    items: items.slice(current * size, (current + 1) * size),
    page: current,
    pages,
    total: items.length,
  }
}

/** Page through a list, newest first as given; `resetOn` returns to the first page. */
export function usePaged<T>(items: readonly T[], size: number, resetOn?: unknown) {
  const [state, setState] = useState({ page: 0, resetOn })
  const page = state.resetOn === resetOn ? state.page : 0
  return {
    ...pageOf(items, page, size),
    setPage: (next: number) => {
      setState({ page: next, resetOn })
    },
  }
}
