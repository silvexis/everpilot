import { useState } from 'react'
import { Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { api } from '@/lib/api'
import { CAPABILITY_META, TASK_STATE_META, type TaskState } from '@/types'

const FILTERS: Array<{ value: TaskState | undefined; label: string }> = [
  { value: undefined, label: 'All' },
  { value: 'executing', label: 'Executing' },
  { value: 'pr_open', label: 'PR Open' },
  { value: 'merged', label: 'Merged' },
  { value: 'failed', label: 'Failed' },
]

export function TasksPage() {
  const [state, setState] = useState<TaskState | undefined>(undefined)
  const { data: tasks, isLoading, error } = useQuery({
    queryKey: ['tasks', state],
    queryFn: () => api.listTasks(state),
  })

  return (
    <div className="mx-auto max-w-5xl px-4 py-8">
      <div className="mb-6 flex items-center justify-between">
        <h1 className="text-2xl font-bold text-gray-900">Tasks</h1>
        <div className="flex gap-2">
          {FILTERS.map((filter) => (
            <button
              key={filter.label}
              onClick={() => setState(filter.value)}
              className={`rounded-full px-3 py-1 text-sm font-medium ${
                state === filter.value
                  ? 'bg-gray-900 text-white'
                  : 'bg-white text-gray-600 hover:bg-gray-100'
              }`}
            >
              {filter.label}
            </button>
          ))}
        </div>
      </div>

      {isLoading && <p className="text-gray-500">Loading tasks…</p>}
      {error && <p className="text-red-600">{(error as Error).message}</p>}
      {tasks && tasks.length === 0 && (
        <p className="rounded-lg border border-dashed border-gray-300 p-8 text-center text-gray-500">
          No tasks yet. Everpilot creates tasks when enabled capabilities react to
          repository activity.
        </p>
      )}

      <ul className="space-y-2">
        {tasks?.map((task) => (
          <li key={task.id}>
            <Link
              to={`/tasks/${task.id}`}
              className="flex items-center justify-between rounded-lg border border-gray-200 bg-white p-4 hover:border-gray-300"
            >
              <div className="flex items-center gap-3">
                <span aria-hidden>{CAPABILITY_META[task.capability].icon}</span>
                <div>
                  <p className="font-medium text-gray-900">{task.title}</p>
                  <p className="text-sm text-gray-500">
                    #{task.id} · {CAPABILITY_META[task.capability].label} · {task.trigger}
                  </p>
                </div>
              </div>
              <span
                className={`rounded-full px-2.5 py-0.5 text-xs font-medium ${TASK_STATE_META[task.state].color}`}
              >
                {TASK_STATE_META[task.state].label}
              </span>
            </Link>
          </li>
        ))}
      </ul>
    </div>
  )
}
