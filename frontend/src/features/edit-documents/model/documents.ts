import {
  MAX_RESOURCES,
  contentDigest,
  emptyDocuments,
  emptySlot,
  isSaved,
  jobModeOf,
} from '@/entities/preparation'
import type { DocumentSlot, DocumentsDraft, ResourceSlot } from '@/entities/preparation'
import { api } from '@/shared/api'
import type {
  DocumentView,
  ExecutionProfile,
  PreparationView,
  ProfileIn,
  ProfileView,
} from '@/shared/api'

/** Uploads in progress, so that the step does not continue before they finish. */
export const UPLOAD_KEY = ['upload-document'] as const

export const ACCEPTED_FILES = '.txt,.md,.json,.xml,.html,.docx,.pdf'
export const MAX_TEXT = 60_000
export const MAX_TITLE = 120

/** The editor of a stored document whose text is `text`. */
export function slotOf(document: DocumentView, text: string): DocumentSlot {
  return {
    documentId: document.id,
    savedDigest: contentDigest(document.title, text),
    text,
    title: document.title,
    filename: document.filename,
    hasOriginal: document.has_original,
    generated: document.origin === 'generated',
    warnings: document.warnings,
  }
}

/** The documents of a saved profile, with the texts of its documents by id. */
export function documentsOf(profile: ProfileView, texts: ReadonlyMap<string, string>) {
  const documents = emptyDocuments()
  const text = (document: DocumentView) => texts.get(document.id) ?? ''
  documents.loadedFrom = profile.id
  if (profile.cv) documents.cv = slotOf(profile.cv, text(profile.cv))
  if (profile.job_offer) {
    documents.offer = slotOf(profile.job_offer, text(profile.job_offer))
    documents.offerSource = profile.job_mode === 'generated' ? 'describe' : 'document'
  }
  documents.resources = profile.resources.map((resource): ResourceSlot => ({
    ...slotOf(resource, text(resource)),
    key: resource.id,
  }))
  return documents
}

/**
 * Load the documents of a preparation with their full texts, to edit them again. They count as
 * loaded from the preparation's profile, if it has one.
 */
export async function loadPreparationDocuments(view: PreparationView): Promise<DocumentsDraft> {
  const of = (kind: string) => view.documents.filter((d) => d.kind === kind)
  const texts = await Promise.all(view.documents.map((d) => api.documentText(d.id)))
  const documents = documentsOf(
    {
      id: view.profile_id ?? '',
      name: '',
      created_at: 0,
      updated_at: 0,
      job_mode: view.job_mode as ProfileView['job_mode'],
      cv: of('cv')[0] ?? null,
      job_offer: of('job_offer')[0] ?? null,
      resources: of('resource'),
    },
    new Map(texts.map((t) => [t.id, t.text])),
  )
  return { ...documents, loadedFrom: view.profile_id }
}

/** Load the documents of a saved profile with their full texts. */
export async function loadProfileDocuments(profile: ProfileView): Promise<DocumentsDraft> {
  const all = [profile.cv, profile.job_offer, ...profile.resources].filter(
    (d): d is DocumentView => d !== null,
  )
  const texts = await Promise.all(all.map((d) => api.documentText(d.id)))
  return documentsOf(profile, new Map(texts.map((t) => [t.id, t.text])))
}

const hasContent = (slot: DocumentSlot) => slot.documentId !== null || slot.text.trim() !== ''

export type Problem =
  | { kind: 'cv' }
  | { kind: 'offer' }
  | { kind: 'resource-title'; index: number }
  | { kind: 'resource-content'; index: number }
  | { kind: 'too-many-resources' }

/** What is missing before the documents can be analysed; nothing when they are complete. */
export function problemsOf(documents: DocumentsDraft): Problem[] {
  const problems: Problem[] = []
  if (!hasContent(documents.cv) || !documents.cv.text.trim()) problems.push({ kind: 'cv' })
  if (documents.offerSource !== 'none' && !documents.offer.text.trim())
    problems.push({ kind: 'offer' })
  documents.resources.forEach((resource, index) => {
    if (!resource.title.trim()) problems.push({ kind: 'resource-title', index })
    if (!resource.text.trim()) problems.push({ kind: 'resource-content', index })
  })
  if (documents.resources.length > MAX_RESOURCES) problems.push({ kind: 'too-many-resources' })
  return problems
}

/**
 * Store every editor that holds unsaved text: typed text becomes a new document, edited text a
 * revision of the document it came from (the uploaded original stays available).
 */
export async function storeDocuments(documents: DocumentsDraft): Promise<DocumentsDraft> {
  const store = async <S extends DocumentSlot>(slot: S, kind: 'cv' | 'job_offer' | 'resource') => {
    if (isSaved(slot)) return slot
    const title = slot.title.trim() || (kind === 'cv' ? 'CV' : 'Job offer')
    const view = slot.documentId
      ? await api.reviseDocument(slot.documentId, { text: slot.text, title })
      : await api.typedDocument({ kind, title, text: slot.text, generated: slot.generated })
    return { ...slot, ...slotOf(view, slot.text.trim()) }
  }
  const offer =
    documents.offerSource === 'none' ? documents.offer : await store(documents.offer, 'job_offer')
  const resources: ResourceSlot[] = []
  for (const resource of documents.resources) resources.push(await store(resource, 'resource'))
  return { ...documents, cv: await store(documents.cv, 'cv'), offer, resources }
}

/** The profile content for stored documents. */
export function profileBody(name: string, documents: DocumentsDraft): ProfileIn {
  return {
    name: name.trim(),
    cv_id: documents.cv.documentId,
    job_offer_id: documents.offerSource === 'none' ? null : documents.offer.documentId,
    resources: documents.resources.map((r) => ({
      title: r.title.trim(),
      document_id: r.documentId ?? '',
    })),
  }
}

/** Whether stored documents differ from a saved profile. */
export function differsFrom(documents: DocumentsDraft, profile: ProfileView): boolean {
  const body = profileBody(profile.name, documents)
  return (
    body.cv_id !== (profile.cv?.id ?? null) ||
    body.job_offer_id !== (profile.job_offer?.id ?? null) ||
    body.resources.length !== profile.resources.length ||
    body.resources.some((r, i) => {
      const saved = profile.resources[i]
      return saved === undefined || r.document_id !== saved.id || r.title !== saved.title
    })
  )
}

export const clearedSlot = (slot: DocumentSlot): DocumentSlot => emptySlot(slot.title)

/** Analyse stored documents in a new preparation, owned by `profileId` when given. */
export function prepareDocuments(
  documents: DocumentsDraft,
  options: { language: 'it' | 'en'; execution: ExecutionProfile; profileId: string | null },
): Promise<PreparationView> {
  const offer = documents.offerSource === 'none' ? null : documents.offer
  return api.prepare({
    language: options.language,
    job_mode: jobModeOf(documents),
    cv_id: documents.cv.documentId,
    job_offer_id: offer?.documentId ?? null,
    resources: documents.resources.map((r) => ({
      title: r.title.trim(),
      document_id: r.documentId ?? '',
    })),
    profile_id: options.profileId,
    execution_profile: options.execution,
  })
}
