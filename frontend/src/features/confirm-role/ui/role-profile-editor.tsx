import { CheckIcon } from 'lucide-react'

import type { PreparationView, RoleProfileData } from '@/shared/api'
import { useMessages } from '@/shared/i18n'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/shared/ui/card'
import { Input } from '@/shared/ui/input'
import { RequiredMark } from '@/shared/ui/required-mark'
import { Textarea } from '@/shared/ui/textarea'
import { roleMessages } from './messages'

/**
 * Edit the target role of a preparation. The caller keeps unconfirmed edits (`role`), so they
 * survive leaving the page; `null` shows the preparation's own role. Approving the review
 * confirms the role as it is shown (`confirmRole`). Without a preparation, as in a start
 * without documents, the caller's role is the only one.
 */
export function RoleProfileEditor({
  preparation,
  role: edited,
  onEdit,
}: {
  preparation?: PreparationView
  role: RoleProfileData | null
  onEdit: (role: RoleProfileData | null) => void
}) {
  const t = useMessages(roleMessages)
  const role = edited ?? preparation?.role_profile
  if (!role) return null
  const update = (patch: Partial<RoleProfileData>) => {
    onEdit({ ...role, ...patch, confirmed: false })
  }
  return (
    <Card data-testid="role-profile">
      <CardHeader>
        <CardTitle role="heading" aria-level={2}>
          {t.title}
        </CardTitle>
        <CardDescription>{t.hint}</CardDescription>
      </CardHeader>
      <CardContent>
        <div className="flex flex-col gap-4">
          {role.rationale && (
            <p className="text-sm text-muted-foreground">
              <strong>{t.proposal}:</strong> {role.rationale}
            </p>
          )}
          <div className="grid gap-4 md:grid-cols-3">
            {(['profession', 'target_role', 'seniority'] as const).map((key) => (
              <div key={key} className="flex flex-col gap-2">
                <label htmlFor={`role-${key}`} className="text-sm font-medium">
                  {t[key]} <RequiredMark />
                </label>
                <Input
                  id={`role-${key}`}
                  required
                  maxLength={160}
                  value={role[key]}
                  onChange={(e) => {
                    update({ [key]: e.target.value })
                  }}
                />
              </div>
            ))}
          </div>
          <div className="grid gap-4 md:grid-cols-2">
            {(['responsibilities', 'competencies'] as const).map((key) => (
              <div key={key} className="flex flex-col gap-2">
                <label htmlFor={`role-${key}`} className="text-sm font-medium">
                  {t[key]}
                </label>
                <Textarea
                  id={`role-${key}`}
                  className="flex-1"
                  rows={4}
                  maxLength={4812}
                  value={role[key].join('\n')}
                  onChange={(e) => {
                    update({ [key]: e.target.value.split('\n') })
                  }}
                />
              </div>
            ))}
          </div>
          <p className="text-sm text-muted-foreground">{t.lines}</p>
          {role.confirmed && (
            <p className="flex items-center gap-1 text-sm text-success">
              <CheckIcon className="size-4" aria-hidden="true" />
              {t.confirmed}
            </p>
          )}
        </div>
      </CardContent>
    </Card>
  )
}
