import type { JobStatus, Profile, ProfileInput, StartJobInput } from './types'

export class ApiError extends Error {}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`/api${path}`, {
    headers: init?.body ? { 'Content-Type': 'application/json' } : undefined,
    ...init,
  })

  if (!response.ok) {
    throw new ApiError(await readErrorMessage(response))
  }
  return response.status === 204 ? (undefined as T) : ((await response.json()) as T)
}

async function readErrorMessage(response: Response): Promise<string> {
  try {
    const body = await response.json()
    // FastAPI returns a string detail for HTTPException and a list for validation errors.
    if (typeof body.detail === 'string') return body.detail
    if (Array.isArray(body.detail)) return body.detail.map((e: { msg: string }) => e.msg).join(', ')
  } catch {
    /* fall through to the status text */
  }
  return `${response.status} ${response.statusText}`
}

export const api = {
  listProfiles: () => request<Profile[]>('/users'),

  createProfile: (input: ProfileInput) =>
    request<Profile>('/users', { method: 'POST', body: JSON.stringify(input) }),

  updateProfile: (id: number, input: Partial<ProfileInput>) =>
    request<Profile>(`/users/${id}`, { method: 'PATCH', body: JSON.stringify(input) }),

  deleteProfile: (id: number) => request<void>(`/users/${id}`, { method: 'DELETE' }),

  getSession: () => request<{ stored: boolean }>('/session'),

  clearSession: () => request<void>('/session', { method: 'DELETE' }),

  getJob: () => request<JobStatus>('/jobs/current'),

  startJob: (input: StartJobInput) =>
    request<JobStatus>('/jobs/current', { method: 'POST', body: JSON.stringify(input) }),

  stopJob: () => request<JobStatus>('/jobs/current/stop', { method: 'POST' }),

  submitCode: (code: string) =>
    request<JobStatus>('/jobs/current/code', {
      method: 'POST',
      body: JSON.stringify({ code }),
    }),

  releaseJob: () => request<JobStatus>('/jobs/current/release', { method: 'POST' }),
}
