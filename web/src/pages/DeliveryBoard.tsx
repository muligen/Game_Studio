import { useEffect, useState } from 'react'
import { useQuery, useQueryClient, useMutation } from '@tanstack/react-query'
import { useSearchParams, Link } from 'react-router-dom'
import { useWorkspace } from '@/lib/workspace'
import { deliveryApi } from '@/lib/api'
import type { DeliveryTask, KickoffDecisionGate, AcceptanceRun } from '@/lib/api'
import { DeliveryTaskCard } from '@/components/board/DeliveryTaskCard'
import { DeliveryTaskDetailDrawer } from '@/components/board/DeliveryTaskDetailDrawer'
import { KickoffDecisionGateCard } from '@/components/board/KickoffDecisionGateCard'
import { KickoffDecisionDialog } from '@/components/common/KickoffDecisionDialog'
import { PoolStatusBar } from '@/components/common/PoolStatusBar'
import { useWebSocket } from '@/hooks/useWebSocket'

const COLUMNS = [
  { key: 'gate', title: 'Kickoff Decision Needed', status: 'gate' },
  { key: 'preview', title: 'Preview', status: 'preview' },
  { key: 'blocked', title: 'Blocked', status: 'blocked' },
  { key: 'ready', title: 'Ready', status: 'ready' },
  { key: 'in_progress', title: 'In Progress', status: 'in_progress' },
  { key: 'review', title: 'Review', status: 'review' },
  { key: 'done', title: 'Done', status: 'done' },
] as const

export function DeliveryBoard() {
  const { workspace } = useWorkspace()
  const queryClient = useQueryClient()
  const { connected, subscribe } = useWebSocket()
  const [searchParams] = useSearchParams()
  const requirementId = searchParams.get('requirement_id') || undefined
  const [resolveGate, setResolveGate] = useState<KickoffDecisionGate | null>(null)
  const [selectedTask, setSelectedTask] = useState<DeliveryTask | null>(null)

  const { data: board, isLoading, error } = useQuery({
    queryKey: ['delivery-board', workspace, requirementId],
    queryFn: () => deliveryApi.listBoard(workspace, requirementId),
  })

  useEffect(() => {
    if (connected) subscribe(workspace)
  }, [connected, workspace, subscribe])

  useEffect(() => {
    const handleMessage = (e: Event) => {
      const message = (e as CustomEvent).detail
      if (
        message.type === 'entity_changed' &&
        ['delivery_plan', 'delivery_task', 'decision_gate'].includes(message.entity_type)
      ) {
        queryClient.invalidateQueries({ queryKey: ['delivery-board'] })
      }
    }
    window.addEventListener('ws-message', handleMessage as EventListener)
    return () => window.removeEventListener('ws-message', handleMessage as EventListener)
  }, [queryClient])

  const startMutation = useMutation({
    mutationFn: (taskId: string) => deliveryApi.startTask(workspace, taskId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['delivery-board'] })
    },
  })

  const retryMutation = useMutation({
    mutationFn: (taskId: string) => deliveryApi.retryTask(workspace, taskId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['delivery-board'] })
      queryClient.invalidateQueries({ queryKey: ['pool-status'] })
    },
  })

  const retryAcceptanceMutation = useMutation({
    mutationFn: (planId: string) => deliveryApi.retryAcceptance(workspace, planId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['delivery-board'] })
    },
  })

  if (isLoading) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <p className="text-gray-600">Loading delivery board...</p>
      </div>
    )
  }

  if (error) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <p className="text-red-600">Error: {error.message}</p>
      </div>
    )
  }

  const gates = board?.decision_gates.filter((g) => g.status === 'open') || []
  const tasks = board?.tasks || []
  const plans = board?.plans || []
  const acceptanceRuns = board?.acceptance_runs || []
  const tasksByStatus = (status: string) => tasks.filter((t) => t.status === status)

  const activePlan = plans[0]
  const latestRun = acceptanceRuns.length > 0
    ? acceptanceRuns[acceptanceRuns.length - 1]
    : null as AcceptanceRun | null
  const showAcceptanceBanner = activePlan && ['validating', 'repairing', 'accepted', 'needs_attention'].includes(activePlan.status)

  return (
    <div className="min-h-screen bg-gray-100">
      <div className="container mx-auto px-4 py-8 space-y-6">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-4">
            <h1 className="text-3xl font-bold text-gray-900">Delivery Board</h1>
            {requirementId && (
              <span className="text-sm text-gray-500 font-mono">
                Filtered: {requirementId}
                <Link to="/delivery" className="ml-2 text-blue-600 hover:underline">Clear</Link>
              </span>
            )}
          </div>
          <Link to="/" className="text-sm text-blue-600 hover:underline">&larr; Workbench</Link>
        </div>
        <PoolStatusBar />
        {showAcceptanceBanner && (
          <div className={`rounded-lg p-4 border ${
            activePlan.status === 'accepted' ? 'bg-emerald-50 border-emerald-200' :
            activePlan.status === 'needs_attention' ? 'bg-red-50 border-red-200' :
            activePlan.status === 'validating' ? 'bg-blue-50 border-blue-200' :
            'bg-amber-50 border-amber-200'
          }`}>
            <div className="flex items-center justify-between">
              <div>
                <h3 className="font-semibold text-sm">
                  {activePlan.status === 'accepted' && 'Acceptance Passed'}
                  {activePlan.status === 'needs_attention' && 'Acceptance Failed'}
                  {activePlan.status === 'validating' && 'Running Acceptance Validation...'}
                  {activePlan.status === 'repairing' && 'Repairing Failed Criteria...'}
                </h3>
                {latestRun && (
                  <p className="text-xs text-muted-foreground mt-1">
                    Attempt {latestRun.attempt_number} &mdash;
                    {' '}{latestRun.criteria_results.filter((c) => c.status === 'passed').length}/{latestRun.criteria_results.length} criteria passed
                    {latestRun.criteria_results.some((c) => c.status === 'failed' && c.blocking) && (
                      <span className="text-red-600 ml-1">
                        ({latestRun.criteria_results.filter((c) => c.status === 'failed' && c.blocking).length} blocking)
                      </span>
                    )}
                  </p>
                )}
                {latestRun && latestRun.criteria_results.filter((c) => c.status !== 'passed').length > 0 && (
                  <div className="mt-2 space-y-1">
                    {latestRun.criteria_results
                      .filter((c) => c.status !== 'passed')
                      .slice(0, 3)
                      .map((cr) => (
                        <div key={cr.criterion_id} className="text-xs">
                          <span className={cr.status === 'failed' ? 'text-red-700' : 'text-amber-700'}>
                            {cr.status === 'failed' ? '✗' : '?'}
                          </span>
                          {' '}{cr.reason}
                        </div>
                      ))}
                    {latestRun.criteria_results.filter((c) => c.status !== 'passed').length > 3 && (
                      <div className="text-xs text-muted-foreground">
                        +{latestRun.criteria_results.filter((c) => c.status !== 'passed').length - 3} more
                      </div>
                    )}
                  </div>
                )}
              </div>
              {activePlan.status === 'needs_attention' && (
                <button
                  className="px-3 py-1.5 text-sm bg-red-600 text-white rounded hover:bg-red-700"
                  onClick={() => retryAcceptanceMutation.mutate(activePlan.id)}
                  disabled={retryAcceptanceMutation.isPending}
                >
                  {retryAcceptanceMutation.isPending ? 'Retrying...' : 'Retry Acceptance'}
                </button>
              )}
            </div>
          </div>
        )}
        <div className="flex gap-6 overflow-x-auto pb-4">
          {COLUMNS.map((col) => (
            <div key={col.key} className="flex-shrink-0 w-80">
              <h2 className="font-semibold mb-4 text-sm uppercase text-gray-600">
                {col.title} ({col.key === 'gate' ? gates.length : tasksByStatus(col.status).length})
              </h2>
              <div className="space-y-3">
                {col.key === 'gate'
                  ? gates.map((gate) => (
                      <KickoffDecisionGateCard
                        key={gate.id}
                        gate={gate}
                        onResolve={() => setResolveGate(gate)}
                      />
                    ))
                  : tasksByStatus(col.status).map((task) => (
                      <DeliveryTaskCard
                        key={task.id}
                        task={task}
                        onClick={() => setSelectedTask(task)}
                        onStart={
                          task.status === 'ready'
                            ? () => startMutation.mutate(task.id)
                            : undefined
                        }
                        onRetry={
                          task.status === 'failed'
                            ? () => retryMutation.mutate(task.id)
                            : undefined
                        }
                      />
                    ))}
              </div>
            </div>
          ))}
        </div>
      </div>
      {resolveGate && (
        <KickoffDecisionDialog
          gate={resolveGate}
          workspace={workspace}
          open={!!resolveGate}
          onOpenChange={(open) => { if (!open) setResolveGate(null) }}
        />
      )}
      <DeliveryTaskDetailDrawer
        task={selectedTask}
        workspace={workspace}
        open={Boolean(selectedTask)}
        onOpenChange={(open) => { if (!open) setSelectedTask(null) }}
      />
    </div>
  )
}
