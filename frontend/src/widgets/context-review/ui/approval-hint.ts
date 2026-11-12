import type { PreparationView, RoleProfileData } from '@/shared/api'
import { useMessages } from '@/shared/i18n'
import { approvalBlock } from '../model/preparation'
import { contextReviewMessages } from './messages'

/** Why approving is not possible yet, as a hint for the button that approves. */
export function useApprovalHint(
  view: PreparationView | undefined,
  role: RoleProfileData | null,
): string | undefined {
  const t = useMessages(contextReviewMessages)
  const block = approvalBlock(view, role)
  return block === null ? undefined : t.missing[block]
}
