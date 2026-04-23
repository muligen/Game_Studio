import { useQuery, useQueryClient } from '@tanstack/react-query'
import { useEffect, useState } from 'react'
import { ProductWorkbenchHeader } from '@/components/board/ProductWorkbenchHeader'
import { ProductLifecycleBoard } from '@/components/board/ProductLifecycleBoard'
import { CreateRequirementDialog } from '@/components/common/CreateRequirementDialog'
import { RequirementClarificationDialog } from '@/components/common/RequirementClarificationDialog'
import { PoolStatusBar } from '@/components/common/PoolStatusBar'
import { requirementsApi } from '@/lib/api'
import { useWorkspace } from '@/lib/workspace'
import { useWebSocket } from '@/hooks/useWebSocket'
import { deriveProductWorkbenchState } from '@/lib/product-workbench'

export function RequirementsBoard() {
  const { workspace } = useWorkspace()
  const queryClient = useQueryClient()
  const { connected, subscribe } = useWebSocket()
  const [clarifyReq, setClarifyReq] = useState<{ id: string; title: string } | null>(null)
  const [showCreate, setShowCreate] = useState(false)

  const { data: requirements, isLoading, error } = useQuery({
    queryKey: ['requirements', workspace],
    queryFn: () => requirementsApi.list(workspace),
  })

  useEffect(() => {
    if (connected) {
      subscribe(workspace)
    }
  }, [connected, workspace, subscribe])

  useEffect(() => {
    const handleMessage = (e: Event) => {
      const message = (e as CustomEvent).detail
      if (message.type === 'entity_changed' && message.entity_type === 'requirement') {
        queryClient.invalidateQueries({ queryKey: ['requirements'] })
      }
    }

    window.addEventListener('ws-message', handleMessage as EventListener)
    return () => {
      window.removeEventListener('ws-message', handleMessage as EventListener)
    }
  }, [queryClient])

  const handleCardClick = (_id: string) => {
    // TODO: navigate to requirement detail page
  }

  const workbench = deriveProductWorkbenchState(requirements || [])

  if (isLoading) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <p className="text-gray-600">Loading product workbench...</p>
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
      <div className="container mx-auto px-4 py-8 space-y-6">
        <h1 className="text-3xl font-bold text-gray-900">Current Product Workbench</h1>

        <ProductWorkbenchHeader
          baselineStatus={workbench.baselineStatus}
          onCreateRequirement={() => setShowCreate(true)}
          onContinueClarifying={() => {
            if (workbench.mvpRequirement) {
              setClarifyReq({
                id: workbench.mvpRequirement.id,
                title: workbench.mvpRequirement.title,
              })
            }
          }}
          mvpRequirementId={workbench.mvpRequirement?.id}
        />

        {requirements && requirements.length > 0 ? (
          <ProductLifecycleBoard
            requirements={requirements}
            onCardClick={handleCardClick}
            workspace={workspace}
            onClarify={(id, title) => setClarifyReq({ id, title })}
            requirementKinds={workbench.requirementKinds}
          />
        ) : (
          <div className="bg-white rounded-lg shadow-md p-8 text-center">
            <p className="text-gray-500 mb-2">No requirements yet</p>
            <p className="text-gray-400 text-sm">Create your first requirement to define the product MVP.</p>
          </div>
        )}

        <div className="mt-6">
          <PoolStatusBar />
        </div>
      </div>

      {showCreate && (
        <CreateRequirementDialog
          workspace={workspace}
          baselineStatus={workbench.baselineStatus}
          open={showCreate}
          onOpenChange={(open) => { if (!open) setShowCreate(false) }}
        />
      )}

      {clarifyReq && (
        <RequirementClarificationDialog
          workspace={workspace}
          requirementId={clarifyReq.id}
          requirementTitle={clarifyReq.title}
          requirementKind={workbench.requirementKinds.get(clarifyReq.id) || 'product_mvp'}
          open={!!clarifyReq}
          onOpenChange={(open) => { if (!open) setClarifyReq(null) }}
        />
      )}
    </div>
  )
}
