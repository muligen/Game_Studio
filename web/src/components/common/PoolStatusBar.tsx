import { Badge } from '@/components/ui/badge'
import { poolApi } from '@/lib/api'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { useEffect, useState } from 'react'

const AGENT_COLORS: Record<string, string> = {
  design: 'bg-blue-100 text-blue-800',
  dev: 'bg-purple-100 text-purple-800',
  qa: 'bg-orange-100 text-orange-800',
  quality: 'bg-green-100 text-green-800',
  art: 'bg-pink-100 text-pink-800',
}

export function PoolStatusBar() {
  const queryClient = useQueryClient()
  const [showErrors, setShowErrors] = useState(false)
  const [expandedErrors, setExpandedErrors] = useState<Set<number>>(new Set())

  const { data: pool } = useQuery({
    queryKey: ['pool-status'],
    queryFn: () => poolApi.status(),
    refetchInterval: 5000,
  })

  // Refresh on WebSocket pool events
  useEffect(() => {
    const handleMessage = (e: Event) => {
      const message = (e as CustomEvent).detail
      if (message.type === 'entity_changed' && message.entity_type === 'pool') {
        queryClient.invalidateQueries({ queryKey: ['pool-status'] })
      }
    }
    window.addEventListener('ws-message', handleMessage as EventListener)
    return () => window.removeEventListener('ws-message', handleMessage as EventListener)
  }, [queryClient])

  if (!pool) return null

  const stuckCount = pool.tasks?.filter(t => t.running_duration_seconds > 300).length ?? 0
  const errorCount = pool.recent_errors?.length ?? 0

  return (
    <div className="bg-white rounded-lg shadow-sm border p-4">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <span className="text-sm font-medium text-gray-700">Agent Pool</span>
          <span className="text-xs text-gray-500">
            {pool.active_count}/{pool.max_workers} workers
            {pool.queued_count > 0 && (
              <span className="text-amber-600 ml-1">({pool.queued_count} queued)</span>
            )}
            {errorCount > 0 && (
              <button
                className="text-red-600 font-semibold ml-1 hover:underline"
                onClick={() => setShowErrors(!showErrors)}
              >
                ({errorCount} errors)
              </button>
            )}
            {stuckCount > 0 && (
              <span className="text-amber-600 font-semibold ml-1">({stuckCount} stuck)</span>
            )}
          </span>
        </div>
        <div className="flex items-center gap-2">
          {pool.idle ? (
            <Badge className="bg-gray-100 text-gray-600">Idle</Badge>
          ) : (
            pool.tasks.map((task) => (
              <Badge key={task.task_id} className={AGENT_COLORS[task.agent_type] || 'bg-gray-100 text-gray-600'}>
                {task.agent_type}: {task.requirement_title || task.requirement_id}
              </Badge>
            ))
          )}
        </div>
      </div>

      {showErrors && pool.recent_errors && pool.recent_errors.length > 0 && (
        <div className="mt-2 border-t pt-2 max-h-80 overflow-y-auto space-y-1">
          {[...pool.recent_errors].reverse().map((err, i) => {
            const expanded = expandedErrors.has(i)
            const toggle = () => {
              const next = new Set(expandedErrors)
              if (next.has(i)) next.delete(i)
              else next.add(i)
              setExpandedErrors(next)
            }
            const detail: Record<string, unknown> = (err.details as Record<string, unknown>) || {}
            return (
              <div key={i} className="text-xs py-0.5">
                <div className="flex items-start justify-between gap-1">
                  <div className="min-w-0">
                    <span className={err.error_type === 'stuck' ? 'text-amber-600' : 'text-red-600'}>
                      [{err.error_type}]
                      {detail.exception_type ? ` ${String(detail.exception_type)}` : ''}
                    </span>{' '}
                    <span className="text-gray-700">{err.agent_type}: {err.error_message}</span>
                  </div>
                  {!!(detail.traceback || detail.prompt) && (
                    <button
                      className="text-blue-600 hover:underline shrink-0"
                      onClick={toggle}
                    >
                      {expanded ? '−' : '+'}
                    </button>
                  )}
                </div>
                {expanded && (
                  <div className="mt-1 ml-4 space-y-1">
                    {!!detail.prompt && (
                      <details open>
                        <summary className="text-gray-500 cursor-pointer">Prompt</summary>
                        <pre className="mt-0.5 text-gray-600 whitespace-pre-wrap break-all bg-gray-50 p-1 rounded max-h-32 overflow-y-auto font-mono text-[10px]">
                          {String(detail.prompt)}
                        </pre>
                      </details>
                    )}
                    {!!detail.traceback && (
                      <details>
                        <summary className="text-gray-500 cursor-pointer">Traceback</summary>
                        <pre className="mt-0.5 text-red-600 whitespace-pre-wrap break-all bg-gray-50 p-1 rounded max-h-32 overflow-y-auto font-mono text-[10px]">
                          {String(detail.traceback)}
                        </pre>
                      </details>
                    )}
                  </div>
                )}
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}
