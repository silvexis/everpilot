import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Link, useParams } from 'react-router-dom'
import { CapabilityToggle } from '@/components/CapabilityToggle'
import { api } from '@/lib/api'
import type { CapabilityKey, CapabilityMode } from '@/types'

export function RepoDetailPage() {
  const { owner, repo } = useParams<{ owner: string; repo: string }>()
  const fullName = `${owner}/${repo}`
  const queryClient = useQueryClient()

  const { data: config, isLoading, error } = useQuery({
    queryKey: ['repo', fullName],
    queryFn: () => api.getRepoConfig(fullName),
  })

  const updateCapability = useMutation({
    mutationFn: ({
      capability,
      mode,
      enabled,
    }: {
      capability: CapabilityKey
      mode: CapabilityMode
      enabled: boolean
    }) => api.updateCapability(fullName, capability, mode, enabled),
    onSuccess: (updated) => {
      queryClient.setQueryData(['repo', fullName], updated)
    },
  })

  return (
    <div className="mx-auto max-w-4xl px-4 py-10 sm:px-6 lg:px-8">
      {/* Breadcrumb */}
      <nav className="mb-6 flex items-center gap-2 text-sm text-gray-500">
        <Link to="/dashboard" className="hover:text-gray-900">
          Dashboard
        </Link>
        <span>/</span>
        <span className="text-gray-900">{fullName}</span>
      </nav>

      <div className="mb-8 flex items-start justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">{repo}</h1>
          <p className="mt-1 text-sm text-gray-500">
            Configure which capabilities Everpilot manages for <strong>{fullName}</strong>.
          </p>
        </div>
        <a
          href={`https://github.com/${fullName}`}
          target="_blank"
          rel="noreferrer"
          className="rounded-md border border-gray-300 px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50"
        >
          View on GitHub ↗
        </a>
      </div>

      {isLoading && (
        <div className="py-16 text-center text-gray-400">Loading configuration…</div>
      )}

      {error && (
        <div className="rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-700">
          Failed to load configuration: {(error as Error).message}
        </div>
      )}

      {config && (
        <>
          <div className="mb-4 flex items-center gap-2">
            <h2 className="text-lg font-semibold text-gray-900">Capabilities</h2>
            {updateCapability.isPending && (
              <span className="text-xs text-gray-400">Saving…</span>
            )}
          </div>
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            {config.capabilities.map((cap) => (
              <CapabilityToggle
                key={cap.capability}
                config={cap}
                disabled={updateCapability.isPending}
                onChange={(capability, mode, enabled) =>
                  updateCapability.mutate({ capability, mode, enabled })
                }
              />
            ))}
          </div>

          <div className="mt-10 border-t border-gray-200 pt-6">
            <h3 className="mb-2 text-sm font-medium text-gray-900">Danger zone</h3>
            <button
              type="button"
              className="rounded-md border border-red-300 px-4 py-2 text-sm font-medium text-red-600 hover:bg-red-50"
              onClick={async () => {
                if (confirm(`Uninstall Everpilot from ${fullName}?`)) {
                  await api.uninstallRepo(fullName)
                  queryClient.invalidateQueries({ queryKey: ['repos'] })
                  window.location.href = '/dashboard'
                }
              }}
            >
              Uninstall Everpilot from this repo
            </button>
          </div>
        </>
      )}
    </div>
  )
}
