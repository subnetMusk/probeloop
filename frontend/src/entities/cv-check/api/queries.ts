import { queryOptions } from '@tanstack/react-query'

import { api } from '@/shared/api'

/** Every approved context with a CV review, latest review first. */
export const cvCheckHistoryQuery = queryOptions({
  queryKey: ['history', 'cv-checks'],
  queryFn: () => api.cvCheckHistory(),
})

/** The CV checks with at least one version that belongs to a profile. */
export const profileCvChecksQuery = (profileId: string) =>
  queryOptions({
    queryKey: ['history', 'cv-checks', profileId],
    queryFn: () => api.cvCheckHistory(profileId),
  })
