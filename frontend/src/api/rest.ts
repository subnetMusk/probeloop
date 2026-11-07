import type { components } from './types/rest'

export type CreateSession = components['schemas']['CreateSession']
export type SessionView = components['schemas']['SessionView']
export type SpeechStatus = components['schemas']['SpeechStatusView']
export type SessionSummary = components['schemas']['SessionSummaryView']
export type TurnView = components['schemas']['TurnView']
export type WordView = components['schemas']['WordView']
export type JobView = components['schemas']['JobView']

export class ApiError extends Error {
  constructor(
    readonly status: number,
    message: string,
  ) {
    super(message)
  }
}

const JSON_HEADERS = { 'Content-Type': 'application/json' }

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
  if (response.status === 204) return undefined as T
  return (await response.json()) as T
}

const sessionPath = (id: string) => `/api/sessions/${encodeURIComponent(id)}`

export const api = {
  speechStatus: () => request<SpeechStatus>('/api/speech'),
  sessions: () => request<SessionSummary[]>('/api/sessions'),
  session: (id: string) => request<SessionView>(sessionPath(id)),
  createSession: (body: CreateSession) =>
    request<SessionView>('/api/sessions', {
      method: 'POST',
      headers: JSON_HEADERS,
      body: JSON.stringify(body),
    }),
  deleteSession: (id: string) => request<undefined>(sessionPath(id), { method: 'DELETE' }),
  editAnswer: (id: string, turnSeq: number, text: string) =>
    request<SessionView>(`${sessionPath(id)}/answers/${String(turnSeq)}`, {
      method: 'PUT',
      headers: JSON_HEADERS,
      body: JSON.stringify({ text }),
    }),
  refine: (id: string) => request<JobView>(`${sessionPath(id)}/refine`, { method: 'POST' }),
  sessionJobs: (id: string) => request<JobView[]>(`${sessionPath(id)}/jobs`),
}

/** Where a session file (an export or an audio file) can be downloaded. */
export const sessionFile = (id: string, name: string) => `${sessionPath(id)}/files/${name}`

export const isRunning = (job: JobView | undefined) =>
  job !== undefined && (job.status === 'queued' || job.status === 'running')
