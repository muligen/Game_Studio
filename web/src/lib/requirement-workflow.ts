import type {
  ClarificationSession,
  DeliverySummary,
  KickoffTaskStatus,
  RequirementCard,
} from './api'

export type RequirementWorkflowPhase =
  | 'no_brief'
  | 'clarifying'
  | 'brief_ready'
  | 'meeting_queued'
  | 'meeting_running'
  | 'meeting_failed'
  | 'meeting_complete'
  | 'delivery_generating'
  | 'delivery_failed'
  | 'delivery_ready'
  | 'delivery_active'

export type WorkflowActionId =
  | 'start_clarifying'
  | 'continue_clarifying'
  | 'edit_brief'
  | 'start_meeting'
  | 'view_meeting'
  | 'retry_meeting'
  | 'reopen_brief'
  | 'generate_delivery'
  | 'retry_delivery_generation'
  | 'open_delivery'
  | 'view_minutes'

export interface WorkflowAction {
  id: WorkflowActionId
  label: string
  disabled?: boolean
}

export interface WorkflowProgressStep {
  id: 'clarify' | 'meeting' | 'delivery'
  label: string
  status: 'done' | 'active' | 'failed' | 'pending'
}

export interface RequirementWorkflowState {
  phase: RequirementWorkflowPhase
  phaseLabel: string
  primaryAction: WorkflowAction
  secondaryActions: WorkflowAction[]
  progressSteps: WorkflowProgressStep[]
  canOpenClarify: boolean
  canOpenMeeting: boolean
  canOpenDelivery: boolean
  showMeetingGraph: boolean
}

export interface DeriveRequirementWorkflowInput {
  requirement: RequirementCard
  clarificationSession: ClarificationSession | null
  kickoffTask: KickoffTaskStatus | null
  deliverySummary: DeliverySummary | null
}

const PHASE_LABELS: Record<RequirementWorkflowPhase, string> = {
  no_brief: 'No Brief',
  clarifying: 'Clarifying Brief',
  brief_ready: 'Brief Ready',
  meeting_queued: 'Meeting Queued',
  meeting_running: 'Meeting Running',
  meeting_failed: 'Meeting Failed',
  meeting_complete: 'Meeting Complete',
  delivery_generating: 'Generating Delivery',
  delivery_failed: 'Delivery Generation Failed',
  delivery_ready: 'Delivery Ready',
  delivery_active: 'Delivery Active',
}

function action(id: WorkflowActionId, label: string, disabled = false): WorkflowAction {
  return { id, label, ...(disabled ? { disabled } : {}) }
}

function hasDelivery(summary: DeliverySummary | null): boolean {
  return Boolean(summary && (summary.plan_count > 0 || summary.tasks.total > 0))
}

function hasActiveDelivery(summary: DeliverySummary | null): boolean {
  return Boolean(summary && (summary.tasks.in_progress > 0 || summary.latest_plan_status === 'active'))
}

function derivePhase({
  requirement,
  clarificationSession,
  kickoffTask,
  deliverySummary,
}: DeriveRequirementWorkflowInput): RequirementWorkflowPhase {
  if (hasActiveDelivery(deliverySummary)) return 'delivery_active'
  if (hasDelivery(deliverySummary)) return 'delivery_ready'

  if (kickoffTask) {
    if (kickoffTask.status === 'pending') return 'meeting_queued'
    if (kickoffTask.status === 'running') return 'meeting_running'
    if (kickoffTask.status === 'failed' && kickoffTask.meeting_result) return 'delivery_failed'
    if (kickoffTask.status === 'failed') return 'meeting_failed'
    if (kickoffTask.status === 'completed') return 'meeting_complete'
  }

  if (clarificationSession?.status === 'kickoff_started') return 'meeting_queued'
  if (clarificationSession?.status === 'completed') return 'meeting_complete'
  if (clarificationSession?.status === 'ready') return 'brief_ready'
  if (clarificationSession?.status === 'collecting' || clarificationSession?.status === 'failed') {
    return 'clarifying'
  }

  if (requirement.status === 'pending_user_review') return 'brief_ready'
  if (requirement.status === 'designing') return 'clarifying'
  if (requirement.status === 'approved') return 'meeting_complete'
  if (
    requirement.status === 'implementing' ||
    requirement.status === 'testing' ||
    requirement.status === 'self_test_passed' ||
    requirement.status === 'pending_user_acceptance' ||
    requirement.status === 'quality_check' ||
    requirement.status === 'done'
  ) {
    return 'delivery_active'
  }

  return 'no_brief'
}

function primaryActionForPhase(
  phase: RequirementWorkflowPhase,
  options: { meetingReady: boolean },
): WorkflowAction {
  const { meetingReady } = options
  switch (phase) {
    case 'no_brief':
      return action('start_clarifying', 'Start Clarifying')
    case 'clarifying':
      return action('continue_clarifying', 'Continue Clarifying')
    case 'brief_ready':
      return action('start_meeting', 'Start Meeting', !meetingReady)
    case 'meeting_queued':
    case 'meeting_running':
    case 'delivery_generating':
      return action('view_meeting', 'View Meeting')
    case 'meeting_failed':
      return action('retry_meeting', 'Retry Meeting', !meetingReady)
    case 'meeting_complete':
      return action('generate_delivery', 'Generate Delivery')
    case 'delivery_failed':
      return action('retry_delivery_generation', 'Retry Delivery Generation')
    case 'delivery_ready':
    case 'delivery_active':
      return action('open_delivery', 'Open Delivery')
  }
}

function secondaryActionsForPhase(phase: RequirementWorkflowPhase): WorkflowAction[] {
  switch (phase) {
    case 'brief_ready':
      return [action('edit_brief', 'Edit Brief')]
    case 'meeting_failed':
      return [action('view_meeting', 'View Meeting'), action('reopen_brief', 'Reopen Brief')]
    case 'meeting_complete':
      return [action('view_meeting', 'View Meeting'), action('view_minutes', 'View Minutes')]
    case 'delivery_failed':
      return [action('view_meeting', 'View Meeting'), action('view_minutes', 'View Minutes')]
    case 'delivery_ready':
    case 'delivery_active':
      return [action('view_meeting', 'View Meeting')]
    default:
      return []
  }
}

function progressForPhase(phase: RequirementWorkflowPhase): WorkflowProgressStep[] {
  const clarifyDone = !['no_brief', 'clarifying'].includes(phase)
  const meetingDone = ['meeting_complete', 'delivery_generating', 'delivery_failed', 'delivery_ready', 'delivery_active'].includes(phase)
  const deliveryDone = phase === 'delivery_ready' || phase === 'delivery_active'

  return [
    {
      id: 'clarify',
      label: 'Clarify',
      status: phase === 'no_brief' || phase === 'clarifying' ? 'active' : 'done',
    },
    {
      id: 'meeting',
      label: 'Meeting',
      status: phase === 'meeting_failed' ? 'failed' : meetingDone ? 'done' : clarifyDone ? 'active' : 'pending',
    },
    {
      id: 'delivery',
      label: 'Delivery',
      status: phase === 'delivery_failed' ? 'failed' : deliveryDone ? 'done' : meetingDone ? 'active' : 'pending',
    },
  ]
}

export function deriveRequirementWorkflowState(
  input: DeriveRequirementWorkflowInput,
): RequirementWorkflowState {
  const phase = derivePhase(input)
  const meetingReady = Boolean(input.clarificationSession?.readiness?.ready)

  return {
    phase,
    phaseLabel: PHASE_LABELS[phase],
    primaryAction: primaryActionForPhase(phase, { meetingReady }),
    secondaryActions: secondaryActionsForPhase(phase),
    progressSteps: progressForPhase(phase),
    canOpenClarify: phase === 'no_brief' || phase === 'clarifying' || phase === 'brief_ready',
    canOpenMeeting: [
      'meeting_queued',
      'meeting_running',
      'meeting_failed',
      'meeting_complete',
      'delivery_generating',
      'delivery_failed',
      'delivery_ready',
      'delivery_active',
    ].includes(phase),
    canOpenDelivery: phase === 'delivery_ready' || phase === 'delivery_active',
    showMeetingGraph: [
      'meeting_queued',
      'meeting_running',
      'meeting_failed',
      'meeting_complete',
      'delivery_generating',
      'delivery_failed',
      'delivery_ready',
      'delivery_active',
    ].includes(phase),
  }
}
