import { useState } from 'react'
import { useParams } from 'react-router-dom'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api } from '@/lib/api'
import { CAPABILITY_META, TASK_STATE_META } from '@/types'

export function TaskDetailPage() {
  const { taskId } = useParams()
  const id = Number(taskId)
  const queryClient = useQueryClient()
  const [rollbackResult, setRollbackResult] = useState<string | null>(null)

  const { data: task, isLoading, error } = useQuery({
    queryKey: ['task', id],
    queryFn: () => api.getTask(id),
    enabled: Number.isFinite(id),
  })
  const { data: audit } = useQuery({
    queryKey: ['task-audit', id],
    queryFn: () => api.getTaskAudit(id),
    enabled: Number.isFinite(id),
  })

  const rollback = useMutation({
    mutationFn: () => api.rollbackTask(id, 'requested via dashboard'),
    onSuccess: (data) => {
      setRollbackResult(`Revert PR #${data.revert_pr_number} opened — review and merge it on GitHub.`)
      queryClient.invalidateQueries({ queryKey: ['task-audit', id] })
    },
    onError: (err) => setRollbackResult((err as Error).message),
  })

  if (isLoading) return <p className="p-8 text-gray-500">Loading task…</p>
  if (error || !task)
    return <p className="p-8 text-red-600">{(error as Error)?.message ?? 'Task not found'}</p>

  return (
    <div className="mx-auto max-w-3xl px-4 py-8">
      <div className="mb-6 rounded-lg border border-gray-200 bg-white p-6">
        <div className="mb-2 flex items-center justify-between">
          <h1 className="text-xl font-bold text-gray-900">
            {CAPABILITY_META[task.capability].icon} {task.title}
          </h1>
          <span
            className={`rounded-full px-2.5 py-0.5 text-xs font-medium ${TASK_STATE_META[task.state].color}`}
          >
            {TASK_STATE_META[task.state].label}
          </span>
        </div>
        <p className="text-sm text-gray-500">
          Task #{task.id} · {CAPABILITY_META[task.capability].label} · triggered by{' '}
          {task.trigger}
          {task.pr_number != null && <> · PR #{task.pr_number}</>}
        </p>

        {task.state === 'merged' && task.pr_number != null && (
          <div className="mt-4 border-t border-gray-100 pt-4">
            <button
              onClick={() => rollback.mutate()}
              disabled={rollback.isPending}
              className="rounded-md bg-red-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-red-700 disabled:opacity-50"
            >
              {rollback.isPending ? 'Opening revert PR…' : 'Roll back this change'}
            </button>
            {rollbackResult && <p className="mt-2 text-sm text-gray-600">{rollbackResult}</p>}
          </div>
        )}
      </div>

      <h2 className="mb-3 text-lg font-semibold text-gray-900">Audit trail</h2>
      <ol className="space-y-2">
        {audit?.map((event, index) => (
          <li
            key={event.id ?? index}
            className="rounded-lg border border-gray-200 bg-white px-4 py-3"
          >
            <div className="flex items-center justify-between">
              <span className="font-mono text-sm text-gray-900">{event.event_type}</span>
              <span className="text-xs text-gray-500">
                {event.actor}
                {event.created_at && <> · {new Date(event.created_at).toLocaleString()}</>}
              </span>
            </div>
            {Object.keys(event.payload).length > 0 && (
              <pre className="mt-1 overflow-x-auto text-xs text-gray-500">
                {JSON.stringify(event.payload)}
              </pre>
            )}
          </li>
        ))}
        {audit?.length === 0 && <p className="text-gray-500">No audit events.</p>}
      </ol>
    </div>
  )
}
