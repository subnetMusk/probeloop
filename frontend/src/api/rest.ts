import type { components } from './types/rest'

export type CreateSession = components['schemas']['CreateSession']
export type SessionView = components['schemas']['SessionView']
export type SpeechStatus = components['schemas']['SpeechStatusView']

export class ApiError extends Error {
  constructor(
    readonly status: number,
    message: string,
  ) {
    super(message)
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(path, init)
  if (!response.ok) {
    let detail = response.statusText
    try {
      const body = (await response.json()) as { detail?: unknown }
      if (typeof body.detail === 'string') detail = body.detail
    } catch {
      // keep the status text
    }
    throw new ApiError(response.status, detail)
  }
  return (await response.json()) as T
}

export const api = {
  speechStatus: () => request<SpeechStatus>('/api/speech'),
  session: (id: string) => request<SessionView>(`/api/sessions/${encodeURIComponent(id)}`),
  createSession: (body: CreateSession) =>
    request<SessionView>('/api/sessions', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    }),
}
