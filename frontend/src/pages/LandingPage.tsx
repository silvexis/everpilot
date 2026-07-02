import { Link } from 'react-router-dom'
import { CAPABILITY_META } from '@/types'

export function LandingPage() {
  return (
    <main className="bg-white">
      {/* Hero */}
      <section className="relative overflow-hidden bg-gradient-to-br from-indigo-900 via-indigo-800 to-purple-900 py-24 text-white">
        <div className="mx-auto max-w-4xl px-4 text-center sm:px-6 lg:px-8">
          <div className="mb-6 inline-flex items-center gap-2 rounded-full bg-white/10 px-4 py-1.5 text-sm backdrop-blur-sm">
            <span>🚀</span>
            <span>Autonomous code maintenance for GitHub</span>
          </div>
          <h1 className="mb-6 text-5xl font-bold tracking-tight sm:text-6xl">
            Autopilot, not copilot,
            <br />
            for your repositories
          </h1>
          <p className="mx-auto mb-10 max-w-2xl text-xl text-indigo-200">
            Everpilot takes the wheel. Delegate the ongoing care of your codebase — security,
            issues, dependencies, tests, and freshness — with full control over how autonomous
            each capability is.
          </p>
          <div className="flex flex-col items-center gap-4 sm:flex-row sm:justify-center">
            <Link
              to="/dashboard"
              className="rounded-lg bg-white px-8 py-3 text-base font-semibold text-indigo-900 shadow-lg hover:bg-indigo-50"
            >
              Install on GitHub →
            </Link>
            <a
              href="https://github.com/silvexis/everpilot"
              target="_blank"
              rel="noreferrer"
              className="rounded-lg border border-white/30 px-8 py-3 text-base font-semibold text-white hover:bg-white/10"
            >
              View on GitHub
            </a>
          </div>
        </div>
      </section>

      {/* Capabilities */}
      <section className="py-20">
        <div className="mx-auto max-w-6xl px-4 sm:px-6 lg:px-8">
          <div className="mb-12 text-center">
            <h2 className="mb-4 text-3xl font-bold text-gray-900">Five core capabilities</h2>
            <p className="text-lg text-gray-500">
              Each independently toggleable. Each with <strong>autopilot</strong>,{' '}
              <strong>assisted</strong>, or <strong>off</strong> mode.
            </p>
          </div>

          <div className="grid grid-cols-1 gap-6 sm:grid-cols-2 lg:grid-cols-3">
            {Object.entries(CAPABILITY_META).map(([key, meta]) => (
              <div
                key={key}
                className="rounded-xl border border-gray-200 bg-gray-50 p-6 transition-shadow hover:shadow-md"
              >
                <div className="mb-3 text-3xl">{meta.icon}</div>
                <h3 className="mb-2 text-lg font-semibold text-gray-900">{meta.label}</h3>
                <p className="text-sm text-gray-500">{meta.description}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Operating modes */}
      <section className="bg-gray-50 py-20">
        <div className="mx-auto max-w-4xl px-4 text-center sm:px-6 lg:px-8">
          <h2 className="mb-4 text-3xl font-bold text-gray-900">You set the autonomy level</h2>
          <p className="mb-12 text-lg text-gray-500">
            Different capabilities warrant different levels of trust. Everpilot lets you choose.
          </p>
          <div className="grid grid-cols-1 gap-6 sm:grid-cols-3">
            {[
              { mode: 'Autopilot', icon: '🤖', description: 'No human in the loop. Everpilot handles everything end-to-end.' },
              { mode: 'Assisted', icon: '🤝', description: 'Does the work, opens a PR, waits for your approval before merging.' },
              { mode: 'Off', icon: '⏸️', description: 'Capability disabled. Re-enable any time from your dashboard.' },
            ].map(({ mode, icon, description }) => (
              <div key={mode} className="rounded-xl bg-white p-6 shadow-sm">
                <div className="mb-3 text-3xl">{icon}</div>
                <h3 className="mb-2 font-semibold text-gray-900">{mode}</h3>
                <p className="text-sm text-gray-500">{description}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* CTA */}
      <section className="py-20">
        <div className="mx-auto max-w-2xl px-4 text-center">
          <h2 className="mb-4 text-3xl font-bold text-gray-900">Ready to hand over the wheel?</h2>
          <p className="mb-8 text-lg text-gray-500">
            Install Everpilot as a GitHub App and let it start working in minutes.
          </p>
          <Link
            to="/dashboard"
            className="rounded-lg bg-indigo-600 px-8 py-3 text-base font-semibold text-white hover:bg-indigo-700"
          >
            Get started for free →
          </Link>
        </div>
      </section>
    </main>
  )
}
