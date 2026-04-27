import { useEffect, useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { useWorkspace } from '@/lib/workspace'
import { sessionsApi, poolApi } from '@/lib/api'
import { useWebSocket } from '@/hooks/useWebSocket'
import { Badge } from '@/components/ui/badge'

const AGENT_TYPES = ['design', 'dev', 'qa', 'art', 'quality', 'reviewer'] as const

const AGENT_COLORS: Record<string, string> = {
  design: 'border-purple-300 bg-purple-50',
  dev: 'border-blue-300 bg-blue-50',
  qa: 'border-orange-300 bg-orange-50',
  art: 'border-pink-300 bg-pink-50',
  quality: 'border-green-300 bg-green-50',
  reviewer: 'border-indigo-300 bg-indigo-50',
}

const AGENT_BADGE_COLORS: Record<string, string> = {
  design: 'bg-purple-200 text-purple-800',
  dev: 'bg-blue-200 text-blue-800',
  qa: 'bg-orange-200 text-orange-800',
  art: 'bg-pink-200 text-pink-800',
  quality: 'bg-green-200 text-green-800',
  reviewer: 'bg-indigo-200 text-indigo-800',
}

function formatDuration(seconds: number): string {
  const mins = Math.floor(seconds / 60)
  const secs = Math.floor(seconds % 60)
  if (mins > 0) return `${mins}m ${secs}s`
  return `${secs}s`
}

export function Agents() {
  const { workspace } = useWorkspace()
  const queryClient = useQueryClient()
  const { connected, subscribe } = useWebSocket()
  const [showErrors, setShowErrors] = useState(false)

  const { data: pool } = useQuery({
    queryKey: ['pool-status'],
    queryFn: () => poolApi.status(),
    refetchInterval: 5000,
  })

  const { data: sessionsData, isLoading } = useQuery({
    queryKey: ['agent-sessions'],
    queryFn: () => sessionsApi.listAll(workspace),
  })

  useEffect(() => {
    if (connected) subscribe(workspace)
  }, [connected, workspace, subscribe])

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

  const runningAgents = new Set((pool?.tasks as Array<{ agent_type: string }>)?.map(t => t.agent_type) || [])
  const sessions = sessionsData?.sessions || []

  // Group sessions by project
  const projectIds = [...new Set(sessions.map(s => s.project_id))]

  if (isLoading) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <p className="text-gray-600">Loading agents...</p>
      </div>
    )
  }

  if (sessions.length === 0) {
    return (
      <div className="min-h-screen bg-gray-100">
        <div className="container mx-auto px-4 py-8">
          <h1 className="text-3xl font-bold text-gray-900 mb-4">Agents</h1>
          <p className="text-gray-600">
            No agent sessions found. Start a kickoff meeting to create sessions.
          </p>
        </div>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-gray-100">
      <div className="container mx-auto px-4 py-8 space-y-8">
        <div className="flex items-center justify-between">
          <h1 className="text-3xl font-bold text-gray-900">Agents</h1>
          <div className="flex items-center gap-2 text-sm text-gray-600">
            <span>{pool?.active_count ?? 0}/{pool?.max_workers ?? 3} running</span>
            {pool?.queued_count ? (
              <span className="text-amber-600">({pool.queued_count} queued)</span>
            ) : null}
            {pool?.recent_errors && pool.recent_errors.length > 0 ? (
              <span className="text-red-600 font-semibold">
                ({pool.recent_errors.length} errors)
              </span>
            ) : null}
          </div>
        </div>

        {pool?.recent_errors && pool.recent_errors.length > 0 && (
          <div className="bg-red-50 border border-red-200 rounded-lg p-3">
            <button
              className="text-sm text-red-700 font-medium flex items-center gap-1"
              onClick={() => setShowErrors(!showErrors)}
            >
              {showErrors ? '−' : '+'} {pool.recent_errors.length} Recent Agent Errors
            </button>
            {showErrors && (
              <div className="mt-2 space-y-2 max-h-60 overflow-y-auto">
                {[...pool.recent_errors].reverse().map((err, i) => (
                  <div key={i} className="text-xs bg-white rounded p-2 border border-red-100">
                    <div className="font-mono text-red-700">
                      [{err.error_type.toUpperCase()}] {err.agent_type} &mdash; {err.error_message}
                    </div>
                    <div className="text-gray-500 mt-0.5">
                      Task: {err.task_id.slice(0, 12)}... |{' '}
                      {new Date(err.timestamp).toLocaleTimeString()}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {projectIds.map(projectId => {
          const projectSessions = sessions.filter(s => s.project_id === projectId)
          return (
            <div key={projectId} className="space-y-4">
              <h2 className="text-xl font-semibold text-gray-800">
                Project: <span className="font-mono text-sm">{projectId}</span>
              </h2>
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                {AGENT_TYPES.map(agentType => {
                  const session = projectSessions.find(s => s.agent === agentType)
                  if (!session) return null

                  const isRunning = runningAgents.has(agentType)
                  const runningTask = (pool?.tasks as Array<{ agent_type: string; requirement_title: string; running_duration_seconds: number }>)?.find(
                    t => t.agent_type === agentType,
                  )

                  return (
                    <div
                      key={agentType}
                      className={`border rounded-lg p-4 ${AGENT_COLORS[agentType] || 'border-gray-300 bg-gray-50'}`}
                    >
                      <div className="flex justify-between items-start mb-3">
                        <Badge className={AGENT_BADGE_COLORS[agentType] || 'bg-gray-200'}>
                          {agentType}
                        </Badge>
                        <span
                          className={`text-xs px-2 py-1 rounded ${
                            isRunning
                              ? 'bg-blue-500 text-white'
                              : 'bg-gray-200 text-gray-600'
                          }`}
                        >
                          {isRunning ? 'Running' : 'Idle'}
                        </span>
                      </div>

                      {isRunning && runningTask && (
                        <div className="mb-2 space-y-1">
                          <p className="text-xs text-gray-600 truncate">
                            Working: {runningTask.requirement_title || runningTask.agent_type}
                          </p>
                          {runningTask.running_duration_seconds != null && (
                            <p className={`text-xs font-mono ${
                              runningTask.running_duration_seconds > 300
                                ? 'text-amber-600 font-semibold'
                                : 'text-gray-500'
                            }`}>
                              Running for {formatDuration(runningTask.running_duration_seconds)}
                            </p>
                          )}
                        </div>
                      )}

                      <div className="text-xs text-gray-500 mb-3 space-y-1">
                        <div>Session: {session.session_id.slice(0, 12)}...</div>
                        <div>
                          Last used: {new Date(session.last_used_at).toLocaleString()}
                          {isRunning && (() => {
                            const leaseAge = Date.now() - new Date(session.last_used_at).getTime()
                            if (leaseAge > 300_000) {
                              return <span className="text-red-500 ml-1">(lease may be stuck)</span>
                            }
                            return null
                          })()}
                        </div>
                      </div>

                      {isRunning ? (
                        <span className="text-xs text-gray-400">Agent is busy</span>
                      ) : (
                        <Link
                          to={`/agents/${projectId}/${agentType}`}
                          className="text-sm text-blue-600 hover:underline"
                        >
                          View & Chat
                        </Link>
                      )}
                    </div>
                  )
                })}
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}
