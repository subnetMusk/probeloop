import { useQuery } from '@tanstack/react-query'
import { useNavigate } from '@tanstack/react-router'

import { LANGUAGES, nextStep, useDraft } from '@/entities/preparation'
import type { InterviewSettings } from '@/entities/preparation'
import { speechStatusQuery } from '@/features/check-microphone'
import { SettingsForm } from '@/features/interview-settings'
import { api } from '@/shared/api'
import { stepPath } from '../model/paths'
import { StepFooter, StepFrame } from './step-frame'

const FORM = 'interview-settings-form'

export function SettingsStep() {
  const navigate = useNavigate()
  const settings = useDraft((draft) => draft.settings)
  const updateSettings = useDraft((draft) => draft.updateSettings)
  const completeSettings = useDraft((draft) => draft.completeSettings)
  const execution = useQuery({ queryKey: ['execution-profile'], queryFn: api.executionProfile })
  const speech = useQuery(speechStatusQuery)
  const cloudAvailable = execution.data?.chatgpt.plan_usage ?? false
  // The form starts from the server's default profile and the installed voices, so it waits.
  const ready = (execution.isSuccess || execution.isError) && !speech.isPending
  const voices = speech.data?.voices
  const voiced = (language: string) => voices === undefined || Boolean(voices[language])
  const values: InterviewSettings = {
    ...settings,
    language: voiced(settings.language)
      ? settings.language
      : (LANGUAGES.find(voiced) ?? settings.language),
    execution:
      settings.execution ??
      (execution.data?.profile === 'cloud' && cloudAvailable ? 'cloud' : 'local'),
  }
  return (
    <StepFrame
      step="interview-settings"
      required
      footer={<StepFooter step="interview-settings" form={FORM} disabled={!ready} />}
    >
      {ready && (
        <SettingsForm
          id={FORM}
          values={values}
          cloudAvailable={cloudAvailable}
          voices={voices}
          onChange={updateSettings}
          onSubmit={(submitted) => {
            completeSettings(submitted)
            void navigate({ to: stepPath(nextStep(useDraft.getState(), 'interview-settings')) })
          }}
        />
      )}
    </StepFrame>
  )
}
