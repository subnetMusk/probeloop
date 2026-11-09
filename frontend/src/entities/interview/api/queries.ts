import { queryOptions } from '@tanstack/react-query'

import { api } from '@/shared/api'

/** Every interview, newest first, with its latest report. */
export const interviewHistoryQuery = queryOptions({
  queryKey: ['history', 'interviews'],
  queryFn: api.interviewHistory,
})
