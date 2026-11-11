import { zodResolver } from '@hookform/resolvers/zod'
import { useEffect, useMemo } from 'react'
import { Controller, useForm } from 'react-hook-form'

import {
  DIFFICULTIES,
  DURATIONS,
  INTERVIEW_TYPES,
  LANGUAGES,
  settingsSchema,
} from '@/entities/preparation'
import type { InterviewSettings } from '@/entities/preparation'
import { useMessages } from '@/shared/i18n'
import { ChoiceCard } from '@/shared/ui/choice-card'
import { RadioGroup } from '@/shared/ui/radio-group'
import { RequiredMark } from '@/shared/ui/required-mark'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/shared/ui/select'
import { settingsMessages } from './messages'

const LEGEND = 'mb-3 flex items-center gap-1 font-heading text-base font-semibold'

/**
 * The settings of one interview. Every field has a value, so the form is valid from the start,
 * subject to voice availability. Processing tools come from Settings, outside this form.
 * Changes are reported as they happen so the draft keeps them between steps.
 */
export function SettingsForm({
  id,
  values,
  voices,
  onChange,
  onSubmit,
}: {
  id: string
  values: InterviewSettings
  /** Languages with an interviewer voice; undefined while the speech services are unknown. */
  voices: Partial<Record<string, string | null>> | undefined
  onChange: (values: InterviewSettings) => void
  onSubmit: (values: InterviewSettings) => void
}) {
  const t = useMessages(settingsMessages)
  const schema = useMemo(
    () =>
      settingsSchema.refine((s) => voices === undefined || Boolean(voices[s.language]), {
        path: ['language'],
        message: 'no voice',
      }),
    [voices],
  )
  const { control, handleSubmit, subscribe } = useForm<InterviewSettings>({
    resolver: zodResolver(schema),
    defaultValues: values,
    mode: 'onChange',
  })
  useEffect(
    () =>
      subscribe({
        formState: { values: true },
        callback: ({ values: current }) => {
          onChange(current)
        },
      }),
    [subscribe, onChange],
  )

  return (
    <form
      id={id}
      noValidate
      className="flex flex-col gap-8"
      onSubmit={(event) => void handleSubmit(onSubmit)(event)}
    >
      <fieldset>
        <legend className={LEGEND}>
          {t.language.label} <RequiredMark />
        </legend>
        <p className="mb-3 text-sm text-muted-foreground">{t.language.hint}</p>
        <Controller
          control={control}
          name="language"
          render={({ field }) => (
            <RadioGroup
              aria-required
              value={field.value}
              onValueChange={field.onChange}
              className="grid-cols-1 sm:grid-cols-2"
            >
              {LANGUAGES.map((language) => {
                const missing = voices !== undefined && !voices[language]
                return (
                  <ChoiceCard
                    key={language}
                    id={`${id}-language-${language}`}
                    value={language}
                    title={t.language[language]}
                    description={missing ? t.language.noVoice : undefined}
                    disabled={missing}
                  />
                )
              })}
            </RadioGroup>
          )}
        />
      </fieldset>

      <fieldset>
        <legend className={LEGEND}>
          {t.type.label} <RequiredMark />
        </legend>
        <Controller
          control={control}
          name="interviewType"
          render={({ field }) => (
            <RadioGroup
              aria-required
              value={field.value}
              onValueChange={field.onChange}
              className="grid-cols-1 sm:grid-cols-2"
            >
              {INTERVIEW_TYPES.map((type) => (
                <ChoiceCard
                  key={type}
                  id={`${id}-type-${type}`}
                  value={type}
                  title={t.type[type].title}
                  description={t.type[type].description}
                />
              ))}
            </RadioGroup>
          )}
        />
      </fieldset>

      <div className="grid gap-8 sm:grid-cols-2">
        <fieldset>
          <legend className={LEGEND}>
            {t.difficulty.label} <RequiredMark />
          </legend>
          <Controller
            control={control}
            name="difficulty"
            render={({ field }) => (
              <RadioGroup
                aria-required
                value={field.value}
                onValueChange={field.onChange}
                className="grid-cols-3"
              >
                {DIFFICULTIES.map((difficulty) => (
                  <ChoiceCard
                    key={difficulty}
                    id={`${id}-difficulty-${difficulty}`}
                    value={difficulty}
                    title={t.difficulty[difficulty]}
                  />
                ))}
              </RadioGroup>
            )}
          />
        </fieldset>
        <div>
          <label htmlFor={`${id}-duration`} className={LEGEND}>
            {t.duration.label} <RequiredMark />
          </label>
          <Controller
            control={control}
            name="minutes"
            render={({ field }) => (
              <Select
                required
                value={String(field.value)}
                onValueChange={(value) => {
                  field.onChange(Number(value))
                }}
              >
                <SelectTrigger id={`${id}-duration`} className="w-full">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {DURATIONS.map((minutes) => (
                    <SelectItem key={minutes} value={String(minutes)}>
                      {t.duration.minutes(minutes)}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            )}
          />
        </div>
      </div>
    </form>
  )
}
