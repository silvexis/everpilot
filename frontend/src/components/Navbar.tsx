import { Link, useLocation } from 'react-router-dom'
import { clsx } from 'clsx'

export function Navbar() {
  const { pathname } = useLocation()

  return (
    <header className="border-b border-gray-200 bg-white">
      <div className="mx-auto max-w-6xl px-4 sm:px-6 lg:px-8">
        <div className="flex h-16 items-center justify-between">
          <Link to="/" className="flex items-center gap-2 text-xl font-bold text-gray-900">
            <span className="text-2xl">🚀</span>
            <span>Everpilot</span>
          </Link>

          <nav className="flex items-center gap-6">
            <Link
              to="/dashboard"
              className={clsx(
                'text-sm font-medium transition-colors',
                pathname.startsWith('/dashboard')
                  ? 'text-indigo-600'
                  : 'text-gray-500 hover:text-gray-900',
              )}
            >
              Dashboard
            </Link>
            <Link
              to="/tasks"
              className={clsx(
                'text-sm font-medium transition-colors',
                pathname.startsWith('/tasks')
                  ? 'text-indigo-600'
                  : 'text-gray-500 hover:text-gray-900',
              )}
            >
              Tasks
            </Link>
            <a
              href="https://github.com/silvexis/everpilot"
              target="_blank"
              rel="noreferrer"
              className="text-sm font-medium text-gray-500 hover:text-gray-900"
            >
              GitHub
            </a>
            <Link
              to="/dashboard"
              className="rounded-md bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-700"
            >
              Get started
            </Link>
          </nav>
        </div>
      </div>
    </header>
  )
}
