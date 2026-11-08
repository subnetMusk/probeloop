import type { DocumentView, ProfileView } from '@/shared/api'

export interface ResourceRow {
  key: string
  title: string
  text: string
  file: File | null
  document: DocumentView | null
  originalText: string
}

export const emptyResource = (): ResourceRow => ({
  key: crypto.randomUUID(),
  title: '',
  text: '',
  file: null,
  document: null,
  originalText: '',
})

export const hasContent = (row: ResourceRow) => Boolean(row.text.trim() || row.file || row.document)
export const isEmpty = (row: ResourceRow) => !row.title.trim() && !hasContent(row)
export const isComplete = (row: ResourceRow) => Boolean(row.title.trim()) && hasContent(row)

/** Keep one blank row after the last complete resource, up to twenty resources. */
export function withEmptyRow(rows: ResourceRow[]): ResourceRow[] {
  return rows.length < 21 && rows.every(isComplete) ? [...rows, emptyResource()] : rows
}

export function resourcesChanged(rows: ResourceRow[], profile: ProfileView | undefined): boolean {
  const filled = rows.filter((row) => !isEmpty(row))
  const original = profile?.resources ?? []
  return (
    filled.length !== original.length ||
    filled.some((row, index) => {
      const document = original[index]
      return (
        row.document?.id !== document?.id ||
        row.title.trim() !== document?.title ||
        row.text !== row.originalText ||
        row.file !== null
      )
    })
  )
}
