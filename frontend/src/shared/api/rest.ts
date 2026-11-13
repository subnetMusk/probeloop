import type { components } from '@/shared/api/types/rest'
import { getPreferences } from '@/shared/lib/preferences'
import { localizeProblem } from './problem-messages'

export type CreateSession = components['schemas']['CreateSession']
export type SessionView = components['schemas']['SessionView']
export type SpeechStatus = components['schemas']['SpeechStatusView']
export type SessionSummary = components['schemas']['SessionSummaryView']
export type TurnView = components['schemas']['TurnView']
export type WordView = components['schemas']['WordView']
export type JobView = components['schemas']['JobView']
export type DocumentView = components['schemas']['DocumentView']
export type ProfileView = components['schemas']['ProfileView']
export type PreparationView = components['schemas']['PreparationView']
export type RoleProfileData = components['schemas']['RoleProfileData']
export type FactView = components['schemas']['FactView']
export type RequirementDetailView = components['schemas']['RequirementDetailView']
export type Obligation = RequirementDetailView['obligation']
export type SnapshotView = components['schemas']['SnapshotView']
export type PrepareIn = components['schemas']['PrepareIn']
export type ResourceIn = components['schemas']['ResourceIn']
export type ReviewIn = components['schemas']['ReviewIn']
export type AddFactIn = components['schemas']['AddFactIn']
export type ReportData = components['schemas']['ReportData']
export type ProgressGroup = components['schemas']['ProgressGroupView']
export type ExecutionView = components['schemas']['ExecutionView']
export type InstallationView = components['schemas']['InstallationView']
export type ExecutionProfile = string
export type RequirementView = components['schemas']['RequirementView']
export type ProfileIn = components['schemas']['ProfileIn']
export type InterviewHistoryEntry = components['schemas']['InterviewHistoryView']
export type CvCheckHistoryEntry = components['schemas']['CvCheckHistoryView']

export class ApiError extends Error {
  constructor(
    readonly status: number,
    /** The backend's problem detail, in English. */
    readonly detail: string,
  ) {
    // Known problem details are shown in the interface language.
    super(localizeProblem(detail, getPreferences().language))
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
const preparationPath = (id: string) => `/api/preparations/${encodeURIComponent(id)}`
const json = (method: string, body: unknown): RequestInit => ({
  method,
  headers: JSON_HEADERS,
  body: JSON.stringify(body),
})

export const api = {
  installation: () => request<InstallationView>('/api/installation'),
  configureInstallation: (body: components['schemas']['InstallationChoice']) =>
    request<InstallationView>('/api/installation', json('PUT', body)),
  installModel: (identity: string) =>
    request<JobView>(`/api/installation/models/${encodeURIComponent(identity)}`, json('POST', {})),
  installBase: () => request<JobView[]>('/api/installation/base', json('POST', {})),
  pullLocalModel: (role: string) =>
    request<JobView>(`/api/installation/ollama/${encodeURIComponent(role)}`, json('POST', {})),
  ollamaStatus: () => request<{ available: boolean }>('/api/installation/ollama'),
  completeInstallation: () =>
    request<InstallationView>('/api/installation/complete', json('POST', {})),
  setRoleProfile: (id: string, body: RoleProfileData) =>
    request<PreparationView>(`${preparationPath(id)}/role-profile`, json('PUT', body)),
  reportHistory: () => request<ReportData[]>('/api/reports'),
  progress: () => request<ProgressGroup[]>('/api/progress'),
  dataSummary: () => request<Record<string, number>>('/api/data/summary'),
  prepareBackup: () =>
    request<components['schemas']['BackupReady']>('/api/data/backup', json('POST', {})),
  deleteAllData: () =>
    request<undefined>('/api/data/delete-all', json('POST', { confirmation: 'DELETE ALL DATA' })),
  pendingJobs: () => request<JobView[]>('/api/jobs'),
  executionProfile: () => request<ExecutionView>('/api/settings/execution'),
  selectExecutionProfile: (profile: ExecutionProfile) =>
    request<ExecutionView>('/api/settings/execution', json('PUT', { profile })),
  selectExecutionTools: (
    tools: Partial<
      Record<ExecutionView['tools'][number]['id'], ExecutionView['tools'][number]['selected']>
    >,
  ) => request<ExecutionView>('/api/settings/execution', json('PUT', { tools })),
  setAnswerReconstruction: (enabled: boolean) =>
    request<ExecutionView>(
      '/api/settings/execution',
      json('PUT', { answer_reconstruction: enabled }),
    ),
  chatGptSignIn: () =>
    request<components['schemas']['SignInStart']>(
      '/api/settings/chatgpt/sign-in',
      json('POST', {}),
    ),
  chatGptSignOut: () => request<ExecutionView>('/api/settings/chatgpt/sign-out', json('POST', {})),
  saveJevKey: (key: string) =>
    request<ExecutionView>('/api/settings/jev/key', json('PUT', { key })),
  removeJevKey: () => request<ExecutionView>('/api/settings/jev/remove', json('POST', {})),
  interviewReports: (id: string) => request<ReportData[]>(`${sessionPath(id)}/reports`),
  reviewInterview: (id: string, language: 'it' | 'en') =>
    request<JobView>(`${sessionPath(id)}/reports`, json('POST', { language })),
  job: (id: string) => request<JobView>(`/api/jobs/${encodeURIComponent(id)}`),
  report: (id: string) => request<ReportData>(`/api/reports/${encodeURIComponent(id)}`),
  cvReviews: (snapshotId: string) =>
    request<ReportData[]>(`/api/snapshots/${encodeURIComponent(snapshotId)}/cv-reviews`),
  /** Review the CV of an approved context; the report belongs to `profileId`, if given. */
  reviewCv: (
    snapshotId: string,
    language: 'it' | 'en',
    executionProfile?: ExecutionProfile,
    profileId?: string | null,
  ) =>
    request<JobView>(
      `/api/snapshots/${encodeURIComponent(snapshotId)}/cv-reviews`,
      json('POST', {
        language,
        execution_profile: executionProfile,
        profile_id: profileId ?? null,
      }),
    ),
  /** Every version of a CV check, with its context and the documents nothing else keeps. */
  deleteCvCheck: (snapshotId: string) =>
    request<undefined>(`/api/snapshots/${encodeURIComponent(snapshotId)}/cv-reviews`, {
      method: 'DELETE',
    }),
  /** Save the documents of a CV check as a new profile, which then owns the check. */
  profileFromCheck: (snapshotId: string, name: string) =>
    request<ProfileView>(
      `/api/snapshots/${encodeURIComponent(snapshotId)}/profile`,
      json('POST', { name }),
    ),
  snapshot: (id: string) => request<SnapshotView>(`/api/snapshots/${encodeURIComponent(id)}`),
  snapshotJobs: (id: string) => request<JobView[]>(`/api/snapshots/${encodeURIComponent(id)}/jobs`),
  documentText: (id: string) =>
    request<components['schemas']['DocumentTextView']>(`/api/documents/${encodeURIComponent(id)}`),
  uploadDocument: (kind: string, title: string, file: File) => {
    const body = new FormData()
    body.set('kind', kind)
    body.set('title', title)
    body.set('file', file)
    return request<DocumentView>('/api/documents', { method: 'POST', body })
  },
  typedDocument: (body: components['schemas']['TypedDocument']) =>
    request<DocumentView>('/api/documents/text', json('POST', body)),
  /** Edited text becomes a new document; the original stays with earlier preparations. */
  reviseDocument: (id: string, body: components['schemas']['DocumentRevision']) =>
    request<DocumentView>(`/api/documents/${encodeURIComponent(id)}/revisions`, json('POST', body)),
  draftJobOffer: (body: components['schemas']['DraftRequest']) =>
    request<components['schemas']['DraftView']>('/api/job-offers/draft', json('POST', body)),
  profiles: () => request<ProfileView[]>('/api/profiles'),
  saveProfile: (body: ProfileIn, id?: string) =>
    request<ProfileView>(
      id ? `/api/profiles/${encodeURIComponent(id)}` : '/api/profiles',
      json(id ? 'PUT' : 'POST', body),
    ),
  renameProfile: (id: string, name: string) =>
    request<ProfileView>(`/api/profiles/${encodeURIComponent(id)}`, json('PATCH', { name })),
  deleteProfile: (id: string) =>
    request<undefined>(`/api/profiles/${encodeURIComponent(id)}`, { method: 'DELETE' }),
  prepare: (body: PrepareIn) => request<PreparationView>('/api/preparations', json('POST', body)),
  preparation: (id: string) => request<PreparationView>(preparationPath(id)),
  reviewFact: (id: string, factId: string, body: ReviewIn) =>
    request<PreparationView>(
      `${preparationPath(id)}/facts/${encodeURIComponent(factId)}`,
      json('PUT', body),
    ),
  setObligation: (id: string, factId: string, obligation: Obligation) =>
    request<PreparationView>(
      `${preparationPath(id)}/facts/${encodeURIComponent(factId)}/obligation`,
      json('PUT', { obligation }),
    ),
  addFact: (id: string, body: AddFactIn) =>
    request<PreparationView>(`${preparationPath(id)}/facts`, json('POST', body)),
  setArea: (id: string, body: components['schemas']['AreaIn']) =>
    request<PreparationView>(`${preparationPath(id)}/area`, json('PUT', body)),
  approve: (id: string) =>
    request<SnapshotView>(`${preparationPath(id)}/approve`, { method: 'POST' }),
  /** Back to the review after approval; approving the same content again reuses the snapshot. */
  reopen: (id: string) =>
    request<PreparationView>(`${preparationPath(id)}/reopen`, { method: 'POST' }),
  interviewHistory: () => request<InterviewHistoryEntry[]>('/api/history/interviews'),
  cvCheckHistory: (profileId?: string) =>
    request<CvCheckHistoryEntry[]>(
      profileId
        ? `/api/history/cv-checks?profile_id=${encodeURIComponent(profileId)}`
        : '/api/history/cv-checks',
    ),
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
