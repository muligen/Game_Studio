import { Badge } from '@/components/ui/badge'
import type { KickoffTaskStatus } from '@/lib/api'

interface MeetingGraphProgressProps {
  task: KickoffTaskStatus | null
  phase:
    | 'kickoff_running'
    | 'kickoff_failed'
    | 'delivery_generating'
    | 'delivery_failed'
    | 'delivery_ready'
  compact?: boolean
}

const STEPS = [
  { node: 'moderator_prepare', label: 'Prepare', detail: 'Agenda and attendees', optional: false },
  { node: 'agent_opinion', label: 'Agent Opinions', detail: 'Design, dev, QA, art input', optional: false },
  { node: 'moderator_summarize', label: 'Summarize', detail: 'Consensus and conflicts', optional: false },
  { node: 'moderator_discussion', label: 'Discussion', detail: 'Optional conflict round', optional: true },
  { node: 'moderator_minutes', label: 'Minutes', detail: 'Final meeting notes', optional: false },
  { node: 'delivery_plan', label: 'Delivery Plan', detail: 'Tasks and gates', optional: false },
] as const

function statusForStep(
  step: (typeof STEPS)[number],
  task: KickoffTaskStatus | null,
  phase: MeetingGraphProgressProps['phase'],
): 'done' | 'active' | 'failed' | 'skipped' | 'pending' {
  if (phase === 'delivery_ready') return 'done'
  if (phase === 'delivery_failed' && step.node === 'delivery_plan') return 'failed'
  if (phase === 'kickoff_failed' && task?.current_node === step.node) return 'failed'
  if (task?.completed_nodes.includes(step.node)) return 'done'
  if (
    step.optional &&
    task?.completed_nodes.includes('moderator_minutes') &&
    !task.completed_nodes.includes(step.node)
  ) {
    return 'skipped'
  }
  if (task?.current_node === step.node) return 'active'
  if (!task && phase === 'kickoff_running' && step.node === 'moderator_prepare') return 'active'
  return 'pending'
}

function toneFor(status: ReturnType<typeof statusForStep>): string {
  if (status === 'done') return 'border-green-200 bg-green-50 text-green-700'
  if (status === 'active') return 'border-blue-200 bg-blue-50 text-blue-700'
  if (status === 'failed') return 'border-red-200 bg-red-50 text-red-700'
  if (status === 'skipped') return 'border-slate-200 bg-slate-50 text-slate-400'
  return 'border-slate-200 bg-white text-slate-500'
}

function markerFor(status: ReturnType<typeof statusForStep>): string {
  if (status === 'done') return 'ok'
  if (status === 'active') return '...'
  if (status === 'failed') return '!'
  if (status === 'skipped') return '-'
  return ''
}

export function MeetingGraphProgress({ task, phase, compact = false }: MeetingGraphProgressProps) {
  const activeAgents = task?.active_agents ?? []

  if (compact) {
    return (
      <div className="rounded-md border bg-slate-50 p-2">
        <div className="flex flex-wrap gap-1.5">
          {STEPS.map((step) => {
            const status = statusForStep(step, task, phase)
            return (
              <span
                key={step.node}
                className={`rounded border px-2 py-1 text-[11px] font-medium ${toneFor(status)}`}
              >
                {step.label}
              </span>
            )
          })}
        </div>
      </div>
    )
  }

  return (
    <div className="rounded-md border bg-white p-3">
      <div className="mb-3 flex items-center justify-between gap-2">
        <p className="text-sm font-medium text-slate-900">Meeting Graph</p>
        {task?.status && <Badge variant="outline">{task.status}</Badge>}
      </div>

      <div className="grid gap-2 md:grid-cols-3">
        {STEPS.map((step) => {
          const status = statusForStep(step, task, phase)
          const marker = markerFor(status)
          const showAgents = step.node === task?.current_node && activeAgents.length > 0

          return (
            <div
              key={step.node}
              className={`min-h-24 rounded-md border p-3 transition-colors ${toneFor(status)}`}
            >
              <div className="flex items-start gap-2">
                <span className="flex h-5 w-5 shrink-0 items-center justify-center rounded-full border text-xs font-semibold">
                  {marker}
                </span>
                <div className="min-w-0">
                  <p className="text-sm font-semibold">{step.label}</p>
                  <p className="mt-1 text-xs opacity-80">{step.detail}</p>
                  {showAgents && (
                    <p className="mt-2 break-words text-xs">
                      Active: {activeAgents.join(', ')}
                    </p>
                  )}
                  {status === 'skipped' && (
                    <p className="mt-2 text-xs">Skipped</p>
                  )}
                </div>
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}
