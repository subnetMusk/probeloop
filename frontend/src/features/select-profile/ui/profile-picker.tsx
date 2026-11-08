import { useQuery } from '@tanstack/react-query'

import { MAX_PROFILE_NAME } from '@/entities/preparation'
import type { ProfileChoice } from '@/entities/preparation'
import { profilesQuery } from '@/entities/profile'
import type { ProfileView } from '@/shared/api'
import { useMessages } from '@/shared/i18n'
import { useLanguage } from '@/shared/lib/preferences'
import { ChoiceCard } from '@/shared/ui/choice-card'
import { Input } from '@/shared/ui/input'
import { RadioGroup } from '@/shared/ui/radio-group'
import { RequiredMark } from '@/shared/ui/required-mark'
import { profileMessages } from './messages'

const valueOf = (choice: ProfileChoice | null) =>
  choice === null ? '' : choice.kind === 'saved' ? `saved:${choice.id}` : choice.kind

function ProfileSummary({ profile }: { profile: ProfileView }) {
  const t = useMessages(profileMessages)
  const language = useLanguage()
  const offer = profile.job_offer
  const date = new Date(profile.updated_at * 1000).toLocaleDateString(
    language === 'it' ? 'it-IT' : 'en-GB',
    { day: 'numeric', month: 'short', year: 'numeric' },
  )
  return (
    <span className="flex flex-col gap-0.5">
      <span>
        {profile.cv ? t.summary.cv(profile.cv.filename ?? profile.cv.title) : t.summary.noCv}
      </span>
      <span>
        {offer
          ? profile.job_mode === 'generated'
            ? t.summary.generated(offer.title)
            : t.summary.offer(offer.filename ?? offer.title)
          : t.summary.noOffer}
      </span>
      <span>
        {t.summary.resources(profile.resources.length)} · {t.summary.updated(date)}
      </span>
    </span>
  )
}

/** Choose where the documents of the interview come from. */
export function ProfilePicker({
  id,
  choice,
  onChange,
}: {
  id: string
  choice: ProfileChoice | null
  onChange: (choice: ProfileChoice) => void
}) {
  const t = useMessages(profileMessages)
  const profiles = useQuery(profilesQuery)
  const newName = choice?.kind === 'new' ? choice.name : ''

  const select = (value: string) => {
    if (value.startsWith('saved:')) {
      const profile = profiles.data?.find((p) => `saved:${p.id}` === value)
      if (profile) onChange({ kind: 'saved', id: profile.id, name: profile.name })
    } else if (value === 'new') onChange({ kind: 'new', name: newName })
    else if (value === 'none' || value === 'quick') onChange({ kind: value })
  }

  return (
    <fieldset>
      <legend className="mb-3 flex items-center gap-1 font-heading text-base font-semibold">
        {t.legend} <RequiredMark />
      </legend>
      <RadioGroup aria-required value={valueOf(choice)} onValueChange={select} className="gap-6">
        <section aria-labelledby={`${id}-saved`} className="flex flex-col gap-2">
          <h3 id={`${id}-saved`} className="text-sm font-medium text-muted-foreground">
            {t.saved}
          </h3>
          {profiles.isPending && <p className="text-sm text-muted-foreground">{t.loading}</p>}
          {profiles.error && (
            <p role="alert" className="text-sm text-destructive">
              {t.loadError} {profiles.error.message}
            </p>
          )}
          {profiles.data?.length === 0 && (
            <p className="text-sm text-muted-foreground">{t.noSaved}</p>
          )}
          <div className="grid gap-2 sm:grid-cols-2">
            {profiles.data?.map((profile) => (
              <ChoiceCard
                key={profile.id}
                id={`${id}-saved-${profile.id}`}
                value={`saved:${profile.id}`}
                title={profile.name}
                description={<ProfileSummary profile={profile} />}
              />
            ))}
          </div>
        </section>
        <div className="grid gap-2 sm:grid-cols-3">
          <ChoiceCard
            id={`${id}-new`}
            value="new"
            title={t.new.title}
            description={t.new.description}
          />
          <ChoiceCard
            id={`${id}-none`}
            value="none"
            title={t.none.title}
            description={t.none.description}
          />
          <ChoiceCard
            id={`${id}-quick`}
            value="quick"
            title={t.quick.title}
            description={t.quick.description}
          />
        </div>
      </RadioGroup>
      {choice?.kind === 'new' && (
        <div className="mt-4 flex max-w-md flex-col gap-2">
          <label htmlFor={`${id}-name`} className="flex items-center gap-1 text-sm font-medium">
            {t.new.name} <RequiredMark />
          </label>
          <Input
            id={`${id}-name`}
            required
            maxLength={MAX_PROFILE_NAME}
            value={newName}
            aria-invalid={newName.trim() === '' ? true : undefined}
            onChange={(event) => {
              onChange({ kind: 'new', name: event.target.value })
            }}
          />
        </div>
      )}
    </fieldset>
  )
}
