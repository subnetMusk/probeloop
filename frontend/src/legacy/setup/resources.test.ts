import { describe, expect, it } from 'vitest'

import type { DocumentView, ProfileView } from '@/shared/api'
import { emptyResource, isComplete, isEmpty, resourcesChanged, withEmptyRow } from './resources'

const document: DocumentView = {
  id: 'd1',
  title: 'Project notes',
  kind: 'resource',
  origin: 'typed',
  media_type: 'text/plain',
  filename: null,
  chars: 30,
  warnings: [],
  preview: 'Built a Python service.',
}
const profile: ProfileView = {
  id: 'p1',
  name: 'Backend',
  created_at: 0,
  updated_at: 0,
  resources: [document],
}

describe('resource rows', () => {
  it('adds an empty row only when a title and its content are present', () => {
    const empty = emptyResource()
    expect(isEmpty(empty)).toBe(true)
    expect(withEmptyRow([empty])).toHaveLength(1)
    expect(withEmptyRow([{ ...empty, title: 'Notes' }])).toHaveLength(1)
    const full = { ...empty, title: 'Notes', text: 'Built a service.' }
    const rows = withEmptyRow([full])
    expect(rows).toHaveLength(2)
    expect(isComplete(rows[0] ?? empty)).toBe(true)
    expect(isEmpty(rows[1] ?? full)).toBe(true)
    expect(withEmptyRow(rows)).toHaveLength(2)
  })

  it('preserves unchanged profiles and detects title, text, file and order changes', () => {
    const row = {
      ...emptyResource(),
      title: document.title,
      text: document.preview,
      originalText: document.preview,
      document,
    }
    expect(resourcesChanged([row, emptyResource()], profile)).toBe(false)
    expect(resourcesChanged([{ ...row, title: 'New name' }], profile)).toBe(true)
    expect(resourcesChanged([{ ...row, text: 'Different work' }], profile)).toBe(true)
    expect(resourcesChanged([{ ...row, file: { name: 'notes.txt' } as File }], profile)).toBe(true)
    expect(resourcesChanged([], profile)).toBe(true)
    expect(resourcesChanged([row], undefined)).toBe(true)
    expect(resourcesChanged([emptyResource()], undefined)).toBe(false)
  })
})
