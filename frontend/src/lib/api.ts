import type { CapabilityKey, CapabilityMode, RepoConfig } from '@/types'

const BASE = '/api/v1'

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    headers: { 'Content-Type': 'application/json', ...init?.headers },
    ...init,
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(err.detail ?? 'Request failed')
  }
  if (res.status === 204) return undefined as T
  return res.json() as Promise<T>
}

export const api = {
  /** List all repos where Everpilot is installed. */
  listRepos: () => request<string[]>('/repos'),

  /** Get configuration for a specific repo. */
  getRepoConfig: (fullName: string) => {
    const [owner, repo] = fullName.split('/')
    return request<RepoConfig>(`/repos/${owner}/${repo}`)
  },

  /** Install Everpilot on a repo. */
  installRepo: (repoFullName: string) =>
    request<RepoConfig>('/repos', {
      method: 'POST',
      body: JSON.stringify({ repo_full_name: repoFullName }),
    }),

  /** Update a single capability's mode. */
  updateCapability: (
    fullName: string,
    capability: CapabilityKey,
    mode: CapabilityMode,
    enabled: boolean,
  ) => {
    const [owner, repo] = fullName.split('/')
    return request<RepoConfig>(`/repos/${owner}/${repo}/capabilities`, {
      method: 'PATCH',
      body: JSON.stringify({ capability, mode, enabled }),
    })
  },

  /** Uninstall Everpilot from a repo. */
  uninstallRepo: (fullName: string) => {
    const [owner, repo] = fullName.split('/')
    return request<void>(`/repos/${owner}/${repo}`, { method: 'DELETE' })
  },

  /** Health check. */
  health: () => request<{ status: string; version: string; service: string }>('/health'),
}
