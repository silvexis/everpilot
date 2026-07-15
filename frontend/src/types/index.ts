export type CapabilityMode = 'autopilot' | 'assisted' | 'off'

export type CapabilityKey =
  | 'security'
  | 'issue_triage'
  | 'dependencies'
  | 'test_hygiene'
  | 'freshness'

export interface CapabilityConfig {
  capability: CapabilityKey
  mode: CapabilityMode
  enabled: boolean
}

export interface RepoSummary {
  id: number
  full_name: string
  description: string | null
  private: boolean
  html_url: string
  default_branch: string
  language: string | null
  stargazers_count: number
  updated_at: string | null
}

export interface RepoConfig {
  repo_full_name: string
  capabilities: CapabilityConfig[]
  active: boolean
}

export type TaskState =
  | 'triggered'
  | 'queued'
  | 'planning'
  | 'executing'
  | 'pr_open'
  | 'merged'
  | 'rejected'
  | 'failed'

export interface Task {
  id: number
  repository_id: number
  capability: CapabilityKey
  state: TaskState
  trigger: string
  title: string
  pr_number: number | null
  created_at: string | null
  updated_at: string | null
}

export interface AuditEvent {
  id: number | null
  organization_id: number | null
  repository_id: number | null
  task_id: number | null
  actor: string
  event_type: string
  payload: Record<string, unknown>
  created_at: string | null
}

export const TASK_STATE_META: Record<TaskState, { label: string; color: string }> = {
  triggered: { label: 'Triggered', color: 'bg-gray-100 text-gray-700' },
  queued: { label: 'Queued', color: 'bg-gray-100 text-gray-700' },
  planning: { label: 'Planning', color: 'bg-blue-100 text-blue-700' },
  executing: { label: 'Executing', color: 'bg-blue-100 text-blue-700' },
  pr_open: { label: 'PR Open', color: 'bg-amber-100 text-amber-700' },
  merged: { label: 'Merged', color: 'bg-green-100 text-green-700' },
  rejected: { label: 'Rejected', color: 'bg-red-100 text-red-700' },
  failed: { label: 'Failed', color: 'bg-red-100 text-red-700' },
}

export const CAPABILITY_META: Record<CapabilityKey, { label: string; description: string; icon: string }> = {
  security: {
    label: 'Security',
    description: 'Continuously reviews for vulnerabilities and lands fixes.',
    icon: '🛡️',
  },
  issue_triage: {
    label: 'Issue Triage',
    description: 'Reads new issues, classifies them, proposes and ships fixes.',
    icon: '🎫',
  },
  dependencies: {
    label: 'Dependencies',
    description: 'Keeps third-party libraries current; absorbs Dependabot-style updates.',
    icon: '📦',
  },
  test_hygiene: {
    label: 'Test Hygiene',
    description: 'Runs the test suite, diagnoses failures, and opens fixes.',
    icon: '🧪',
  },
  freshness: {
    label: 'Freshness',
    description: 'General modernization so the codebase never rots.',
    icon: '✨',
  },
}
