import { queryOptions } from '@tanstack/react-query'

import { api } from '@/shared/api'

/** The saved resource profiles, newest first as the server lists them. */
export const profilesQuery = queryOptions({ queryKey: ['profiles'], queryFn: api.profiles })
