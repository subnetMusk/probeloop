import { describe, expect, it } from 'vitest'

import {
  canOpen,
  emptyResource,
  firstOpenStep,
  initialDraft,
  isSaved,
  nextStep,
  preparationKeyOf,
  previousStep,
  restoreDraft,
  contentDigest,
  stepDone,
} from './draft'
import type { PreparationDraft } from './draft'

const SETTINGS = {
  language: 'it',
  interviewType: 'technical',
  difficulty: 'medium',
  minutes: 10,
  execution: 'local',
} as const

function stored(id: string, title: string, text: string) {
  return { documentId: id, savedDigest: contentDigest(title, text), title, text }
}

/** A draft whose documents are stored and analysed. */
function prepared(): PreparationDraft {
  const draft = initialDraft()
  draft.settings = { ...SETTINGS }
  draft.settingsDone = true
  draft.profile = { kind: 'none' }
  draft.documents.cv = { ...draft.documents.cv, ...stored('cv1', 'CV', 'Giulia Neri, backend.') }
  draft.preparationId = 'p1'
  draft.preparationKey = preparationKeyOf(draft)
  return draft
}

describe('preparation draft', () => {
  it('opens the steps in order', () => {
    const draft = initialDraft()
    expect(firstOpenStep(draft)).toBe('interview-settings')
    expect(canOpen(draft, 'resource-profile')).toBe(false)
    draft.settings = { ...SETTINGS }
    draft.settingsDone = true
    expect(canOpen(draft, 'resource-profile')).toBe(true)
    expect(canOpen(draft, 'documents')).toBe(false)
    draft.profile = { kind: 'none' }
    expect(firstOpenStep(draft)).toBe('documents')
    expect(canOpen(draft, 'fact-review')).toBe(false)
  })

  it('needs the server default for the execution profile before the settings are done', () => {
    const draft = initialDraft()
    draft.settingsDone = true
    expect(stepDone(draft, 'interview-settings')).toBe(false)
    draft.settings.execution = 'cloud'
    expect(stepDone(draft, 'interview-settings')).toBe(true)
  })

  it('a new profile needs a name', () => {
    const draft = prepared()
    draft.profile = { kind: 'new', name: '  ' }
    expect(stepDone(draft, 'resource-profile')).toBe(false)
    draft.profile = { kind: 'new', name: 'Backend roles' }
    expect(stepDone(draft, 'resource-profile')).toBe(true)
  })

  it('a quick start skips documents but requires a confirmed role', () => {
    const draft = initialDraft()
    draft.settings = { ...SETTINGS }
    draft.settingsDone = true
    draft.profile = { kind: 'quick' }
    expect(canOpen(draft, 'documents')).toBe(false)
    expect(canOpen(draft, 'fact-review')).toBe(true)
    expect(canOpen(draft, 'final-check')).toBe(false)
    expect(firstOpenStep(draft)).toBe('fact-review')
    expect(nextStep(draft, 'resource-profile')).toBe('fact-review')
    expect(previousStep(draft, 'final-check')).toBe('fact-review')
  })

  it('keeps the preparation until its inputs change', () => {
    const draft = prepared()
    expect(stepDone(draft, 'documents')).toBe(true)
    expect(canOpen(draft, 'fact-review')).toBe(true)
    expect(canOpen(draft, 'final-check')).toBe(false)
    draft.snapshotId = 's1'
    expect(canOpen(draft, 'final-check')).toBe(true)

    // An edit that is not stored yet blocks the later steps.
    draft.documents.cv.text = 'Giulia Neri, backend e dati.'
    expect(isSaved(draft.documents.cv)).toBe(false)
    expect(preparationKeyOf(draft)).toBeNull()
    expect(canOpen(draft, 'fact-review')).toBe(false)
    draft.documents.cv.text = 'Giulia Neri, backend.'
    expect(canOpen(draft, 'final-check')).toBe(true)

    // The interview language and the execution profile are inputs of the analysis.
    draft.settings.language = 'en'
    expect(stepDone(draft, 'documents')).toBe(false)
    draft.settings.language = 'it'
    draft.settings.execution = 'cloud'
    expect(stepDone(draft, 'documents')).toBe(false)
    draft.settings.execution = 'local'

    // So are the resources, with their titles.
    const resource = { ...emptyResource(), ...stored('r1', 'Notes', 'Routing notes.') }
    draft.documents.resources = [resource]
    expect(stepDone(draft, 'documents')).toBe(false)
    draft.preparationKey = preparationKeyOf(draft)
    expect(stepDone(draft, 'documents')).toBe(true)
    resource.title = 'Routing'
    expect(isSaved(resource)).toBe(false)
  })

  it('ignores the offer while the interview has none', () => {
    const draft = prepared()
    draft.documents.offer.text = 'An offer that was typed, then dropped.'
    expect(stepDone(draft, 'documents')).toBe(true)
    draft.documents.offerSource = 'document'
    expect(preparationKeyOf(draft)).toBeNull()
  })

  it('starts over when the stored draft does not match the schema', () => {
    expect(restoreDraft(prepared())).toEqual(prepared())
    // A new profile whose name is still being typed is kept.
    const typing = { ...prepared(), profile: { kind: 'new', name: '' } }
    expect(restoreDraft(typing)?.profile).toEqual({ kind: 'new', name: '' })
    expect(restoreDraft({ settings: { language: 'fr' } })).toBeUndefined()
    expect(restoreDraft(null)).toBeUndefined()
  })
})
