import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useEffect, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { ProductWorkbenchHeader } from '@/components/board/ProductWorkbenchHeader'
import { CreateRequirementDialog } from '@/components/common/CreateRequirementDialog'
import { KickoffDetailDialog } from '@/components/common/KickoffDetailDialog'
import { MeetingGraphProgress } from '@/components/common/MeetingGraphProgress'
import { RequirementClarificationDialog } from '@/components/common/RequirementClarificationDialog'
import {
  clarificationsApi,
  deliveryApi,
  requirementsApi,
  type ClarificationSession,
  type DeliverySummary,
  type KickoffTaskStatus,
  type RequirementCard,
} from '@/lib/api'
import { useWorkspace } from '@/lib/workspace'
import { useWebSocket } from '@/hooks/useWebSocket'
import {
  deriveProductWorkbenchState,
  getIterationTitle,
  statusLabel,
} from '@/lib/product-workbench'
import {
  deriveRequirementWorkflowState,
  type RequirementWorkflowState,
  type WorkflowAction,
} from '@/lib/requirement-workflow'
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
  const [kickoffReq, setKickoffReq] = useState<{
    id: string
    title: string
    sessionId: string | null
    taskId: string | null
  } | null>(null)
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
                  const phase = iter.phase
                  const req = iter.requirement
                  const kind = iter.kind
                  const title = getIterationTitle(kind, i)

                  const dotColor =
                    phase === 'active' ? 'bg-blue-500 ring-2 ring-blue-200' :
                    phase === 'queued' ? 'bg-gray-400' :
                    'bg-green-500'

                  const cardBorder =
                    phase === 'active' ? 'border-blue-200 ring-1 ring-blue-100' :
                    phase === 'queued' ? 'border-gray-200 opacity-60' :
                    'border-gray-200'

                  return (
                    <div key={req.id} className="relative pl-12">
                      {/* Dot on the timeline */}
                      <div
                        className={`absolute left-3.5 w-3 h-3 rounded-full border-2 border-white -translate-x-1/2 ${dotColor}`}
                      />

                      {/* Card */}
                      <div className={`bg-white rounded-lg shadow-sm border ${cardBorder} p-4`}>
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
                              {phase === 'queued' && (
                                <span className="text-xs text-gray-400 italic">
                                  Waiting for previous iteration
                                </span>
                              )}
                            </div>

                            <p className="text-sm text-gray-700 mt-1 truncate">{req.title}</p>
                            <p className="text-xs text-gray-400 font-mono mt-0.5">{req.id}</p>
                          </div>

                          <div className="flex flex-col items-end gap-2 shrink-0">
                            {phase === 'active' ? (
                              <>
                                <ActiveIterationActions
                                  workspace={workspace}
                                  requirement={req}
                                  onClarify={() => setClarifyReq({ id: req.id, title: req.title })}
                                  onViewMeeting={(session, task) =>
                                    setKickoffReq({
                                      id: req.id,
                                      title: req.title,
                                      sessionId: session?.id ?? null,
                                      taskId: task?.id ?? session?.kickoff_task_id ?? null,
                                    })
                                  }
                                />
                              </>
                            ) : phase === 'queued' ? (
                              <span className="text-xs text-gray-400">Queued</span>
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

        {/* New iteration button always visible when MVP baseline is established */}
        {workbench.baselineStatus === 'active' && (
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
          onKickoffStarted={(session, response) => {
            setKickoffReq({
              id: clarifyReq.id,
              title: clarifyReq.title,
              sessionId: session.id,
              taskId: response.task_id,
            })
          }}
        />
      )}

      {kickoffReq && (
        <KickoffDetailDialog
          workspace={workspace}
          requirementId={kickoffReq.id}
          requirementTitle={kickoffReq.title}
          sessionId={kickoffReq.sessionId}
          kickoffTaskId={kickoffReq.taskId}
          open={!!kickoffReq}
          onOpenChange={(open) => { if (!open) setKickoffReq(null) }}
          onEditClarification={() => {
            setClarifyReq({ id: kickoffReq.id, title: kickoffReq.title })
            setKickoffReq(null)
          }}
        />
      )}
    </div>
  )
}

function ActiveIterationActions({
  workspace,
  requirement,
  onClarify,
  onViewMeeting,
}: {
  workspace: string
  requirement: RequirementCard
  onClarify: () => void
  onViewMeeting: (session: ClarificationSession | null, task: KickoffTaskStatus | null) => void
}) {
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const sessionQuery = useQuery({
    queryKey: ['clarification-session', workspace, requirement.id],
    queryFn: () => clarificationsApi.getSession(workspace, requirement.id),
    refetchInterval: 5000,
  })
  const session = sessionQuery.data?.session ?? null
  const taskId = session?.kickoff_task_id ?? null
  const taskQuery = useQuery({
    queryKey: ['kickoff-task', workspace, taskId],
    queryFn: () => clarificationsApi.getKickoffTask(workspace, taskId!),
    enabled: Boolean(taskId),
    refetchInterval: (query) => {
      const status = query.state.data?.status
      return status === 'pending' || status === 'running' ? 2000 : 8000
    },
  })
  const task = taskQuery.data ?? null
  const deliverySummaryQuery = useQuery({
    queryKey: ['delivery-summary', requirement.id],
    queryFn: () => requirementsApi.getDeliverySummary(workspace, requirement.id),
    refetchInterval: 8000,
  })
  const deliverySummary = deliverySummaryQuery.data ?? null

  const kickoffMutation = useMutation({
    mutationFn: () => {
      if (!session) throw new Error('Clarification session is missing.')
      return clarificationsApi.kickoff(workspace, requirement.id, session.id)
    },
    onSuccess: (response) => {
      queryClient.invalidateQueries({ queryKey: ['clarification-session', workspace, requirement.id] })
      onViewMeeting(session, {
        id: response.task_id,
        session_id: session?.id ?? '',
        requirement_id: requirement.id,
        workspace,
        project_id: response.project_id,
        status: 'pending',
        error: null,
        meeting_result: null,
        current_node: 'queued',
        completed_nodes: [],
        active_agents: [],
        progress_events: [],
        started_at: null,
        updated_at: null,
      })
    },
  })
  const deliveryMutation = useMutation({
    mutationFn: () => {
      const result = task?.meeting_result
      if (!result) throw new Error('Meeting result is missing.')
      return deliveryApi.generatePlan(workspace, result.meeting_id, result.project_id)
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['delivery-summary', requirement.id] })
    },
  })

  const workflow = deriveRequirementWorkflowState({
    requirement,
    clarificationSession: session,
    kickoffTask: task,
    deliverySummary,
  })

  const runAction = (action: WorkflowAction) => {
    if (action.disabled) return
    if (
      action.id === 'start_clarifying' ||
      action.id === 'continue_clarifying' ||
      action.id === 'edit_brief' ||
      action.id === 'reopen_brief'
    ) {
      onClarify()
      return
    }
    if (action.id === 'start_meeting' || action.id === 'retry_meeting') {
      kickoffMutation.mutate()
      return
    }
    if (action.id === 'view_meeting' || action.id === 'view_minutes' || action.id === 'generate_delivery') {
      onViewMeeting(session, task)
      return
    }
    if (action.id === 'retry_delivery_generation') {
      deliveryMutation.mutate()
      return
    }
    if (action.id === 'open_delivery') {
      navigate(`/delivery?requirement_id=${requirement.id}`)
    }
  }

  const labelFor = (action: WorkflowAction) => {
    if ((action.id === 'start_meeting' || action.id === 'retry_meeting') && kickoffMutation.isPending) {
      return 'Starting...'
    }
    if ((action.id === 'generate_delivery' || action.id === 'retry_delivery_generation') && deliveryMutation.isPending) {
      return 'Generating...'
    }
    return action.label
  }

  return (
    <div className="w-80 space-y-2 text-right">
      <div className="flex flex-wrap items-center justify-end gap-2">
        <span className="rounded bg-slate-100 px-2 py-0.5 text-xs font-medium text-slate-600">
          {workflow.phaseLabel}
        </span>
        <button
          className="text-sm font-medium text-blue-600 hover:underline disabled:text-slate-400 disabled:no-underline"
          disabled={
            workflow.primaryAction.disabled ||
            kickoffMutation.isPending ||
            deliveryMutation.isPending
          }
          onClick={() => runAction(workflow.primaryAction)}
        >
          {labelFor(workflow.primaryAction)}
        </button>
        {workflow.secondaryActions.map((item) => (
          <button
            key={item.id}
            className="text-xs text-blue-600 hover:underline disabled:text-slate-400 disabled:no-underline"
            disabled={item.disabled || kickoffMutation.isPending || deliveryMutation.isPending}
            onClick={() => runAction(item)}
          >
            {labelFor(item)}
          </button>
        ))}
      </div>
      <WorkflowProgressStrip workflow={workflow} />
      {workflow.showMeetingGraph && (
        <MeetingGraphProgress
          task={task}
          phase={
            workflow.phase === 'delivery_failed'
              ? 'delivery_failed'
              : workflow.phase === 'delivery_generating'
                ? 'delivery_generating'
                : workflow.phase === 'delivery_ready' || workflow.phase === 'delivery_active'
                  ? 'delivery_ready'
                  : workflow.phase === 'meeting_complete'
                    ? 'meeting_complete'
                  : workflow.phase === 'meeting_failed'
                    ? 'kickoff_failed'
                    : 'kickoff_running'
          }
          compact
        />
      )}
      {deliverySummary && deliverySummary.tasks.total > 0 && (
        <DeliveryProgress summary={deliverySummary} />
      )}
    </div>
  )
}

function WorkflowProgressStrip({ workflow }: { workflow: RequirementWorkflowState }) {
  return (
    <div className="grid grid-cols-3 gap-1 text-[11px]">
      {workflow.progressSteps.map((step) => {
        const tone =
          step.status === 'done'
            ? 'border-green-200 bg-green-50 text-green-700'
            : step.status === 'active'
              ? 'border-blue-200 bg-blue-50 text-blue-700'
              : step.status === 'failed'
                ? 'border-red-200 bg-red-50 text-red-700'
                : 'border-slate-200 bg-white text-slate-400'
        return (
          <span key={step.id} className={`rounded border px-2 py-1 text-center font-medium ${tone}`}>
            {step.label}
          </span>
        )
      })}
    </div>
  )
}
