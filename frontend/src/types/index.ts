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
