import { queryOptions } from '@tanstack/react-query'

import { api } from '@/shared/api'

/** The latest report of every interview and CV check, grouped by comparability. */
export const progressQuery = queryOptions({ queryKey: ['progress'], queryFn: api.progress })
