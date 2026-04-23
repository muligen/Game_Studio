import { useEffect, useState } from 'react'
import { useQuery, useQueryClient, useMutation } from '@tanstack/react-query'
import { useWorkspace } from '@/lib/workspace'
import { deliveryApi } from '@/lib/api'
import type { KickoffDecisionGate } from '@/lib/api'
import { DeliveryTaskCard } from '@/components/board/DeliveryTaskCard'
import { KickoffDecisionGateCard } from '@/components/board/KickoffDecisionGateCard'
import { KickoffDecisionDialog } from '@/components/common/KickoffDecisionDialog'
import { useWebSocket } from '@/hooks/useWebSocket'

const COLUMNS = [
  { key: 'gate', title: 'Kickoff Decision Needed', status: 'gate' },
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
  const [resolveGate, setResolveGate] = useState<KickoffDecisionGate | null>(null)

  const { data: board, isLoading, error } = useQuery({
    queryKey: ['delivery-board', workspace],
    queryFn: () => deliveryApi.listBoard(workspace),
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
    mutationFn: (taskId: string) => deliveryApi.startTask(workspace, taskId, 'session-placeholder'),
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
  const tasksByStatus = (status: string) => tasks.filter((t) => t.status === status)

  return (
    <div className="min-h-screen bg-gray-100">
      <div className="container mx-auto px-4 py-8 space-y-6">
        <h1 className="text-3xl font-bold text-gray-900">Delivery Board</h1>
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
                        onStart={
                          task.status === 'ready'
                            ? () => startMutation.mutate(task.id)
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
    </div>
  )
}
