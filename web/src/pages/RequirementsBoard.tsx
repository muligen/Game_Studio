import { useQuery, useQueryClient } from '@tanstack/react-query'
import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { ProductWorkbenchHeader } from '@/components/board/ProductWorkbenchHeader'
import { CreateRequirementDialog } from '@/components/common/CreateRequirementDialog'
import { RequirementClarificationDialog } from '@/components/common/RequirementClarificationDialog'
import { PoolStatusBar } from '@/components/common/PoolStatusBar'
import { requirementsApi, type DeliverySummary } from '@/lib/api'
import { useWorkspace } from '@/lib/workspace'
import { useWebSocket } from '@/hooks/useWebSocket'
import {
  deriveProductWorkbenchState,
  getIterationTitle,
  statusLabel,
} from '@/lib/product-workbench'
import { Badge } from '@/components/ui/badge'

const STATUS_COLORS: Record<string, string> = {
  done: 'bg-green-100 text-green-800',
  draft: 'bg-gray-100 text-gray-700',
  designing: 'bg-purple-100 text-purple-800',
  pending_user_review: 'bg-blue-100 text-blue-800',
  approved: 'bg-indigo-100 text-indigo-800',
  implementing: 'bg-amber-100 text-amber-800',
  testing: 'bg-orange-100 text-orange-800',
  pending_user_acceptance: 'bg-cyan-100 text-cyan-800',
  quality_check: 'bg-teal-100 text-teal-800',
}

function DeliveryProgress({ summary }: { summary: DeliverySummary }) {
  const { total, done, in_progress } = summary.tasks
  if (total === 0) return null
  const pct = Math.round((done / total) * 100)
  return (
    <div className="flex items-center gap-2 text-xs">
      <div className="flex-1 h-2 bg-gray-200 rounded-full overflow-hidden max-w-[120px]">
        <div
          className="h-full bg-green-500 rounded-full transition-all"
          style={{ width: `${pct}%` }}
        />
      </div>
      <span className="text-gray-500 font-mono">
        {done}/{total} done
        {in_progress > 0 && <span className="text-amber-500 ml-1">({in_progress} active)</span>}
      </span>
    </div>
  )
}

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
      <div className="container mx-auto px-4 py-8 space-y-6 max-w-3xl">
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
          hasActiveIteration={!!workbench.activeIteration}
        />

        {workbench.iterations.length > 0 && (
          <div className="space-y-4">
            <h2 className="text-lg font-semibold text-gray-700">Iteration Timeline</h2>

            <div className="relative">
              {/* Vertical line */}
              <div className="absolute left-5 top-0 bottom-0 w-0.5 bg-gray-300" />

              <div className="space-y-4">
                {workbench.iterations.map((iter, i) => {
                  const isActive = iter.isActive
                  const req = iter.requirement
                  const kind = iter.kind
                  const title = getIterationTitle(kind, i)

                  return (
                    <div key={req.id} className="relative pl-12">
                      {/* Dot on the timeline */}
                      <div
                        className={`absolute left-3.5 w-3 h-3 rounded-full border-2 border-white -translate-x-1/2 ${
                          isActive ? 'bg-blue-500 ring-2 ring-blue-200' : 'bg-green-500'
                        }`}
                      />

                      {/* Card */}
                      <div
                        className={`bg-white rounded-lg shadow-sm border ${
                          isActive ? 'border-blue-200 ring-1 ring-blue-100' : 'border-gray-200'
                        } p-4`}
                      >
                        <div className="flex items-start justify-between gap-3">
                          <div className="flex-1 min-w-0">
                            <div className="flex items-center gap-2 flex-wrap">
                              <h3 className="font-semibold text-gray-900">{title}</h3>
                              <Badge
                                className={
                                  kind === 'product_mvp'
                                    ? 'bg-amber-100 text-amber-800'
                                    : 'bg-blue-100 text-blue-800'
                                }
                              >
                                {kind === 'product_mvp' ? 'MVP' : 'CR'}
                              </Badge>
                              <span
                                className={`text-xs px-2 py-0.5 rounded font-mono ${
                                  STATUS_COLORS[req.status || 'draft'] || 'bg-gray-100 text-gray-700'
                                }`}
                              >
                                {statusLabel(req.status || 'draft')}
                              </span>
                            </div>

                            <p className="text-sm text-gray-700 mt-1 truncate">{req.title}</p>
                            <p className="text-xs text-gray-400 font-mono mt-0.5">{req.id}</p>
                          </div>

                          <div className="flex flex-col items-end gap-2 shrink-0">
                            {isActive ? (
                              <>
                                {req.status === 'draft' || req.status === 'designing' ? (
                                  <button
                                    className="text-sm text-blue-600 hover:underline"
                                    onClick={() =>
                                      setClarifyReq({ id: req.id, title: req.title })
                                    }
                                  >
                                    {kind === 'product_mvp' ? 'Clarify MVP' : 'Clarify Change'}
                                  </button>
                                ) : req.status === 'pending_user_review' ? (
                                  <button
                                    className="text-sm text-blue-600 hover:underline"
                                    onClick={() =>
                                      setClarifyReq({ id: req.id, title: req.title })
                                    }
                                  >
                                    Start Kickoff
                                  </button>
                                ) : (
                                  <Link
                                    to={`/delivery?requirement_id=${req.id}`}
                                    className="text-sm text-blue-600 hover:underline"
                                  >
                                    View Delivery
                                  </Link>
                                )}
                                <DeliverySummaryLoader
                                  workspace={workspace}
                                  requirementId={req.id}
                                />
                              </>
                            ) : (
                              <Link
                                to={`/delivery?requirement_id=${req.id}`}
                                className="text-xs text-gray-400 hover:underline"
                              >
                                View Result
                              </Link>
                            )}
                          </div>
                        </div>
                      </div>
                    </div>
                  )
                })}
              </div>
            </div>
          </div>
        )}

        {/* New iteration button after MVP baseline established */}
        {workbench.baselineStatus === 'active' && !workbench.activeIteration && (
          <div className="relative pl-12">
            <div className="absolute left-3.5 w-3 h-3 rounded-full border-2 border-dashed border-gray-400 bg-gray-100 -translate-x-1/2" />
            <button
              onClick={() => setShowCreate(true)}
              className="w-full border-2 border-dashed border-gray-300 rounded-lg p-4 text-center text-gray-500 hover:border-blue-400 hover:text-blue-600 transition-colors"
            >
              + Start New Change Request
            </button>
          </div>
        )}

        {/* Empty state */}
        {requirements && requirements.length === 0 && (
          <div className="bg-white rounded-lg shadow-md p-8 text-center">
            <p className="text-gray-500 mb-2">No requirements yet</p>
            <p className="text-gray-400 text-sm">
              Create your first requirement to define the product MVP.
            </p>
          </div>
        )}

        <div className="mt-6">
          <PoolStatusBar />
        </div>
      </div>

      <CreateRequirementDialog
        workspace={workspace}
        baselineStatus={workbench.baselineStatus}
        open={showCreate}
        onOpenChange={(open) => { if (!open) setShowCreate(false) }}
      />

      {clarifyReq && (
        <RequirementClarificationDialog
          workspace={workspace}
          requirementId={clarifyReq.id}
          requirementTitle={clarifyReq.title}
          requirementKind={workbench.iterations.find(it => it.requirement.id === clarifyReq.id)?.kind || 'product_mvp'}
          open={!!clarifyReq}
          onOpenChange={(open) => { if (!open) setClarifyReq(null) }}
        />
      )}
    </div>
  )
}

function DeliverySummaryLoader({
  workspace,
  requirementId,
}: {
  workspace: string
  requirementId: string
}) {
  const { data } = useQuery({
    queryKey: ['delivery-summary', requirementId],
    queryFn: () => requirementsApi.getDeliverySummary(workspace, requirementId),
    refetchInterval: 8000,
  })
  if (!data || data.tasks.total === 0) return null
  return <DeliveryProgress summary={data} />
}
