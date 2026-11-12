import { useMutation } from '@tanstack/react-query'
import { CheckIcon } from 'lucide-react'

import { api } from '@/shared/api'
import type { PreparationView, RoleProfileData } from '@/shared/api'
import { useMessages } from '@/shared/i18n'
import { Alert, AlertDescription } from '@/shared/ui/alert'
import { Button } from '@/shared/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/shared/ui/card'
import { Input } from '@/shared/ui/input'
import { RequiredMark } from '@/shared/ui/required-mark'
import { Textarea } from '@/shared/ui/textarea'
import { roleMessages } from './messages'

/**
 * Edit and confirm the target role of a preparation. The caller keeps unconfirmed edits
 * (`role`), so they survive leaving the page; `null` shows the preparation's own role.
 */
export function RoleProfileEditor({
  preparation,
  role: edited,
  onEdit,
  onChange,
  onReopened,
}: {
  preparation: PreparationView
  role: RoleProfileData | null
  onEdit: (role: RoleProfileData | null) => void
  onChange: (view: PreparationView) => void
  /** Called when confirming reopened an approved preparation. */
  onReopened?: () => void
}) {
  const t = useMessages(roleMessages)
  const role = edited ?? preparation.role_profile
  const confirm = useMutation({
    mutationFn: async () => {
      if (!role) throw new Error('target profile unavailable')
      if (preparation.status === 'approved') {
        await api.reopen(preparation.id)
        onReopened?.()
      }
      return api.setRoleProfile(preparation.id, {
        ...role,
        responsibilities: role.responsibilities.map((s) => s.trim()).filter(Boolean),
        competencies: role.competencies.map((s) => s.trim()).filter(Boolean),
        confirmed: true,
      })
    },
    onSuccess: (view) => {
      onEdit(view.role_profile ?? null)
      onChange(view)
    },
  })
  if (!role) return null
  const update = (patch: Partial<RoleProfileData>) => {
    onEdit({ ...role, ...patch, confirmed: false })
  }
  const valid =
    [role.profession, role.target_role, role.seniority].every((s) => s.trim()) &&
    [...role.responsibilities, ...role.competencies].every((s) => s.length <= 400) &&
    role.responsibilities.filter((s) => s.trim()).length <= 12 &&
    role.competencies.filter((s) => s.trim()).length <= 12
  return (
    <Card data-testid="role-profile">
      <CardHeader>
        <CardTitle role="heading" aria-level={2}>
          {t.title}
        </CardTitle>
        <CardDescription>{t.hint}</CardDescription>
      </CardHeader>
      <CardContent>
        <form
          className="flex flex-col gap-4"
          onSubmit={(event) => {
            event.preventDefault()
            if (valid) confirm.mutate()
          }}
        >
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
          <div className="flex flex-wrap items-center gap-3">
            <Button type="submit" variant="outline" disabled={!valid || confirm.isPending}>
              {t.confirm}
            </Button>
            {role.confirmed && (
              <span className="flex items-center gap-1 text-sm text-success">
                <CheckIcon className="size-4" aria-hidden="true" />
                {t.confirmed}
              </span>
            )}
          </div>
          {confirm.error && (
            <Alert variant="destructive">
              <AlertDescription>{confirm.error.message}</AlertDescription>
            </Alert>
          )}
        </form>
      </CardContent>
    </Card>
  )
}
