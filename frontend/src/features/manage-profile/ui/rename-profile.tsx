import { useMutation, useQueryClient } from '@tanstack/react-query'
import { CheckIcon, PencilIcon, XIcon } from 'lucide-react'
import { useState } from 'react'

import { MAX_PROFILE_NAME } from '@/entities/preparation'
import { profilesQuery } from '@/entities/profile'
import { api } from '@/shared/api'
import type { ProfileView } from '@/shared/api'
import { useMessages } from '@/shared/i18n'
import { Button } from '@/shared/ui/button'
import { Input } from '@/shared/ui/input'
import { manageMessages } from './messages'

/** The name of a profile, renamed in place: Enter saves, Escape cancels. */
export function RenameProfile({
  profile,
  className,
  nameAs: Name = 'span',
}: {
  profile: ProfileView
  className?: string
  /** `h1` when the name is the title of the page. */
  nameAs?: 'span' | 'h1'
}) {
  const t = useMessages(manageMessages)
  const client = useQueryClient()
  const [draft, setDraft] = useState<string | null>(null)
  const rename = useMutation({
    mutationFn: (name: string) => api.renameProfile(profile.id, name),
    onSuccess: (updated) => {
      client.setQueryData(profilesQuery.queryKey, (old) =>
        old?.map((p) => (p.id === updated.id ? updated : p)),
      )
      void client.invalidateQueries({ queryKey: ['history'] })
      setDraft(null)
    },
  })
  if (draft === null)
    return (
      <div className="flex min-w-0 items-center gap-1">
        <Name className={className}>{profile.name}</Name>
        <Button
          type="button"
          variant="ghost"
          size="icon-xs"
          aria-label={t.rename(profile.name)}
          onClick={() => {
            setDraft(profile.name)
          }}
        >
          <PencilIcon />
        </Button>
      </div>
    )
  const valid = draft.trim() !== ''
  return (
    <form
      className="flex min-w-0 flex-col gap-1"
      onSubmit={(event) => {
        event.preventDefault()
        if (valid) rename.mutate(draft.trim())
      }}
    >
      <div className="flex items-center gap-1">
        <Input
          aria-label={t.name}
          autoFocus
          required
          maxLength={MAX_PROFILE_NAME}
          value={draft}
          disabled={rename.isPending}
          className="h-7"
          onChange={(event) => {
            setDraft(event.target.value)
          }}
          onKeyDown={(event) => {
            if (event.key === 'Escape') setDraft(null)
          }}
        />
        <Button type="submit" variant="ghost" size="icon-xs" aria-label={t.save} disabled={!valid}>
          <CheckIcon />
        </Button>
        <Button
          type="button"
          variant="ghost"
          size="icon-xs"
          aria-label={t.cancel}
          onClick={() => {
            setDraft(null)
          }}
        >
          <XIcon />
        </Button>
      </div>
      {rename.error && (
        <p role="alert" className="text-xs text-destructive">
          {rename.error.message}
        </p>
      )}
    </form>
  )
}
