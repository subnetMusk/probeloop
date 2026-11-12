import { MAX_RESOURCES } from '@/entities/preparation'
import { useMessages } from '@/shared/i18n'
import type { Problem } from '../model/documents'
import { documentsMessages } from './messages'

/** The text of what is missing before documents can be used. */
export function useProblemText(): (problem: Problem) => string {
  const t = useMessages(documentsMessages)
  return (problem: Problem) => {
    switch (problem.kind) {
      case 'cv':
        return t.problems.cv
      case 'offer':
        return t.problems.offer
      case 'resource-title':
        return t.problems.resourceTitle(problem.index + 1)
      case 'resource-content':
        return t.problems.resourceContent(problem.index + 1)
      case 'too-many-resources':
        return t.problems.tooMany(MAX_RESOURCES)
    }
  }
}
