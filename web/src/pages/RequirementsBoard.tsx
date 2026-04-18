import { useQuery, useQueryClient } from '@tanstack/react-query'
import { useEffect } from 'react'
import { KanbanBoard } from '@/components/board/KanbanBoard'
import { CreateRequirementDialog } from '@/components/common/CreateRequirementDialog'
import { PoolStatusBar } from '@/components/common/PoolStatusBar'
import { requirementsApi } from '@/lib/api'
import { useWorkspace } from '@/lib/workspace'
import { useWebSocket } from '@/hooks/useWebSocket'

export function RequirementsBoard() {
  const { workspace } = useWorkspace()
  const queryClient = useQueryClient()
  const { connected, subscribe } = useWebSocket()

  const { data: requirements, isLoading, error } = useQuery({
    queryKey: ['requirements', workspace],
    queryFn: () => requirementsApi.list(workspace),
  })

  // Subscribe to workspace updates when WebSocket connects
  useEffect(() => {
    if (connected) {
      subscribe(workspace)
    }
  }, [connected, workspace, subscribe])

  // Listen for WebSocket messages and refresh requirements on entity changes
  useEffect(() => {
    const handleMessage = (e: Event) => {
      const message = (e as CustomEvent).detail
      if (message.type === 'entity_changed' && message.entity_type === 'requirement') {
        // Invalidate and refetch requirements
        queryClient.invalidateQueries({ queryKey: ['requirements'] })
      }
    }

    window.addEventListener('ws-message', handleMessage as EventListener)
    return () => {
      window.removeEventListener('ws-message', handleMessage as EventListener)
    }
  }, [queryClient])

  const handleCardClick = (id: string) => {
    console.log('Clicked requirement:', id)
    alert(`Requirement detail view for "${id}" is coming soon!\n\nThis will navigate to the requirement detail page in the next iteration.`)
    // TODO: Navigate to requirement detail page
  }


  if (isLoading) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <p className="text-gray-600">Loading requirements...</p>
      </div>
    )
  }

  if (error) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <p className="text-red-600">Error loading requirements: {error.message}</p>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-gray-100">
      <div className="container mx-auto px-4 py-8">
        <div className="flex justify-between items-center mb-8">
          <h1 className="text-4xl font-bold text-gray-900">Requirements Board</h1>
          <CreateRequirementDialog workspace={workspace} />
        </div>

        {requirements && requirements.length > 0 ? (
          <KanbanBoard requirements={requirements} onCardClick={handleCardClick} workspace={workspace} />
        ) : (
          <div className="bg-white rounded-lg shadow-md p-8 text-center">
            <p className="text-gray-600 mb-4">No requirements found</p>
            <CreateRequirementDialog workspace={workspace} />
          </div>
        )}

        <div className="mt-6">
          <PoolStatusBar />
        </div>
      </div>
    </div>
  )
}
