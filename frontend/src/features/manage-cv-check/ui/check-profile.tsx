import { useMutation } from '@tanstack/react-query'
import { useNavigate } from '@tanstack/react-router'
import { FileCheckIcon } from 'lucide-react'

import { rememberCvCheckPreparation } from '@/entities/cv-check'
import { api } from '@/shared/api'
import type { ProfileView } from '@/shared/api'
import { useMessages } from '@/shared/i18n'
import { useLanguage } from '@/shared/lib/preferences'
import { Button } from '@/shared/ui/button'
import { prepareProfileCheck } from '../model/start'
import { cvCheckMessages } from './messages'

/**
 * Check the CV of a saved profile: its documents are analysed at once and the review opens,
 * without passing through the new CV check form.
 */
export function CheckProfileCv({ profile }: { profile: ProfileView }) {
  const t = useMessages(cvCheckMessages)
  const language = useLanguage()
  const navigate = useNavigate()
  const start = useMutation({
    mutationFn: async () => {
      const execution = await api.executionProfile()
      return prepareProfileCheck(profile, language, execution.profile)
    },
    onSuccess: (preparation) => {
      rememberCvCheckPreparation(preparation.id)
      void navigate({
        to: '/cv-checks/new/$preparationId',
        params: { preparationId: preparation.id },
      })
    },
  })
  return (
    <>
      <Button
        type="button"
        variant="outline"
        disabled={start.isPending}
        onClick={() => {
          start.mutate()
        }}
      >
        <FileCheckIcon data-icon="inline-start" />
        {start.isPending ? t.checkStarting : t.check}
      </Button>
      {start.error && (
        <p role="alert" className="w-full text-sm text-destructive">
          {start.error.message}
        </p>
      )}
    </>
  )
}
