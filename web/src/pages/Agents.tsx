import { useEffect } from 'react'
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

export function Agents() {
  const { workspace } = useWorkspace()
  const queryClient = useQueryClient()
  const { connected, subscribe } = useWebSocket()

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
          </div>
        </div>

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
                  const runningTask = (pool?.tasks as Array<{ agent_type: string; requirement_title: string }>)?.find(
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
                        <p className="text-xs text-gray-600 mb-2 truncate">
                          Working: {runningTask.requirement_title || runningTask.agent_type}
                        </p>
                      )}

                      <div className="text-xs text-gray-500 mb-3 space-y-1">
                        <div>Session: {session.session_id.slice(0, 12)}...</div>
                        <div>Last used: {new Date(session.last_used_at).toLocaleString()}</div>
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
