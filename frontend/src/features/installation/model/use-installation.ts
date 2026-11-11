import { useQuery } from '@tanstack/react-query'
import { api } from '@/shared/api'

export function useInstallation() {
  return useQuery({ queryKey: ['installation'], queryFn: api.installation, refetchInterval: 3000 })
}
