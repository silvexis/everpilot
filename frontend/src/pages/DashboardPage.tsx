import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { api } from '@/lib/api'

export function DashboardPage() {
  const { data: repos, isLoading, error } = useQuery({
    queryKey: ['repos'],
    queryFn: api.listRepos,
  })

  return (
    <div className="mx-auto max-w-6xl px-4 py-10 sm:px-6 lg:px-8">
      <div className="mb-8 flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Dashboard</h1>
          <p className="mt-1 text-sm text-gray-500">
            Repositories where Everpilot is installed.
          </p>
        </div>
        <a
          href="https://github.com/apps/everpilot/installations/new"
          target="_blank"
          rel="noreferrer"
          className="rounded-md bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-700"
        >
          + Add repository
        </a>
      </div>

      {isLoading && (
        <div className="py-16 text-center text-gray-400">Loading repositories…</div>
      )}

      {error && (
        <div className="rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-700">
          Failed to load repositories: {(error as Error).message}
        </div>
      )}

      {repos && repos.length === 0 && (
        <div className="rounded-xl border-2 border-dashed border-gray-300 py-16 text-center">
          <p className="text-lg font-medium text-gray-500">No repositories yet</p>
          <p className="mt-1 text-sm text-gray-400">
            Install Everpilot on a GitHub repository to get started.
          </p>
          <a
            href="https://github.com/apps/everpilot/installations/new"
            target="_blank"
            rel="noreferrer"
            className="mt-6 inline-block rounded-md bg-indigo-600 px-5 py-2.5 text-sm font-medium text-white hover:bg-indigo-700"
          >
            Install on GitHub →
          </a>
        </div>
      )}

      {repos && repos.length > 0 && (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {repos.map((fullName) => {
            const [owner, repo] = fullName.split('/')
            return (
              <Link
                key={fullName}
                to={`/dashboard/${owner}/${repo}`}
                className="group rounded-lg border border-gray-200 bg-white p-5 shadow-sm transition-shadow hover:shadow-md"
              >
                <div className="flex items-start justify-between">
                  <div>
                    <p className="text-xs text-gray-400">{owner}</p>
                    <h3 className="font-semibold text-gray-900 group-hover:text-indigo-600">
                      {repo}
                    </h3>
                  </div>
                  <span className="text-gray-300 group-hover:text-indigo-400">→</span>
                </div>
                <p className="mt-3 text-xs text-gray-400">Click to configure capabilities</p>
              </Link>
            )
          })}
        </div>
      )}
    </div>
  )
}
