import type { FactView, PreparationView } from '@/shared/api'

export interface RequirementRow {
  id: string
  text: string
  kind: 'requirement' | 'nice_to_have'
  status: 'met' | 'partial' | 'not_shown'
  supporting: string[]
  rationale: string
}

export interface ReviewSummary {
  /** Facts the user should look at: no verified quote, or from a document with warnings. */
  doubtful: FactView[]
  /** How many of them still wait for a decision. */
  open: number
  counts: { declared: number; confirmed: number; excluded: number; total: number }
  requirements: RequirementRow[]
}

/** Whether a fact deserves the user's attention before the interview. */
export function isDoubtful(fact: FactView, warned: ReadonlySet<string>): boolean {
  return fact.origin === 'inferred' || (fact.document_id !== null && warned.has(fact.document_id))
}

const STATUS_ORDER = { not_shown: 0, partial: 1, met: 2 } as const

/** The compact view of a preparation in review: doubtful facts first, requirements by status. */
export function summarise(preparation: PreparationView): ReviewSummary {
  const warned = new Set(preparation.documents.filter((d) => d.warnings.length).map((d) => d.id))
  const facts = new Map(preparation.facts.map((f) => [f.id, f]))
  const doubtful = preparation.facts.filter((f) => isDoubtful(f, warned))
  const requirements = preparation.matches
    .flatMap((match): RequirementRow[] => {
      const requirement = facts.get(match.requirement_id)
      if (!requirement || requirement.review === 'excluded') return []
      const status =
        match.status === 'met' || match.status === 'partial' ? match.status : 'not_shown'
      return [
        {
          id: requirement.id,
          text: requirement.text,
          kind: requirement.kind === 'nice_to_have' ? 'nice_to_have' : 'requirement',
          status,
          supporting: match.fact_ids.flatMap((id) => {
            const fact = facts.get(id)
            return fact && fact.review !== 'excluded' ? [fact.text] : []
          }),
          rationale: match.rationale,
        },
      ]
    })
    .sort((a, b) => STATUS_ORDER[a.status] - STATUS_ORDER[b.status])
  return {
    doubtful,
    open: doubtful.filter((f) => f.review === 'pending').length,
    counts: {
      declared: preparation.facts.filter((f) => f.origin === 'declared').length,
      confirmed: preparation.facts.filter((f) => f.review === 'confirmed').length,
      excluded: preparation.facts.filter((f) => f.review === 'excluded').length,
      total: preparation.facts.length,
    },
    requirements,
  }
}
