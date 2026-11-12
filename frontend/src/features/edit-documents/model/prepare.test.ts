import { afterEach, expect, it, vi } from 'vitest'

import { contentDigest, emptyDocuments, emptyResource } from '@/entities/preparation'
import { api } from '@/shared/api'
import type { PreparationView } from '@/shared/api'
import { prepareDocuments } from './documents'

afterEach(() => {
  vi.restoreAllMocks()
})

it('analyses stored documents without an interview draft', async () => {
  const prepare = vi.spyOn(api, 'prepare').mockResolvedValue({ id: 'p1' } as PreparationView)
  const documents = emptyDocuments()
  documents.cv = {
    ...documents.cv,
    documentId: 'cv1',
    title: 'CV',
    text: 'Giulia Neri',
    savedDigest: contentDigest('CV', 'Giulia Neri'),
  }
  documents.resources = [
    { ...emptyResource(), documentId: 'r1', title: ' Notes ', text: 'Routing' },
  ]
  await prepareDocuments(documents, { language: 'it', execution: 'local', profileId: 'pr1' })
  expect(prepare).toHaveBeenCalledWith({
    language: 'it',
    job_mode: 'none',
    cv_id: 'cv1',
    job_offer_id: null,
    resources: [{ title: 'Notes', document_id: 'r1' }],
    profile_id: 'pr1',
    execution_profile: 'local',
  })
})
