import type { RequirementCard } from './api'

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export type RequirementKind = 'product_mvp' | 'change_request'
export type BaselineStatus = 'not_started' | 'defining_mvp' | 'active'

export type IterationPhase = 'active' | 'queued' | 'completed'

export interface IterationInfo {
  requirement: RequirementCard
  kind: RequirementKind
  phase: IterationPhase
}

export interface ProductWorkbenchState {
  baselineStatus: BaselineStatus
  mvpRequirement: RequirementCard | null
  iterations: IterationInfo[]
  activeIteration: IterationInfo | null
  queuedIterations: IterationInfo[]
  completedIterations: IterationInfo[]
}

// ---------------------------------------------------------------------------
// Derived state
// ---------------------------------------------------------------------------

export function deriveProductWorkbenchState(
  requirements: RequirementCard[],
): ProductWorkbenchState {
  if (requirements.length === 0) {
    return {
      baselineStatus: 'not_started',
      mvpRequirement: null,
      iterations: [],
      activeIteration: null,
      queuedIterations: [],
      completedIterations: [],
    }
  }

  const sorted = [...requirements].sort((a, b) => {
    const aTime = a.created_at || ''
    const bTime = b.created_at || ''
    if (aTime && bTime) return aTime.localeCompare(bTime)
    return a.id.localeCompare(b.id)
  })

  const mvpRequirement = sorted[0]
  const mvpDone = mvpRequirement.status === 'done'
  const baselineStatus: BaselineStatus = mvpDone ? 'active' : 'defining_mvp'

  let seenActive = false
  const iterations: IterationInfo[] = sorted.map((req, i) => {
    const kind: RequirementKind = i === 0 ? 'product_mvp' : 'change_request'
    if (req.status === 'done') {
      return { requirement: req, kind, phase: 'completed' as const }
    }
    if (!seenActive) {
      seenActive = true
      return { requirement: req, kind, phase: 'active' as const }
    }
    return { requirement: req, kind, phase: 'queued' as const }
  })

  const completedIterations = iterations.filter((it) => it.phase === 'completed')
  const activeIteration = iterations.find((it) => it.phase === 'active') || null
  const queuedIterations = iterations.filter((it) => it.phase === 'queued')

  return {
    baselineStatus,
    mvpRequirement,
    iterations,
    activeIteration,
    queuedIterations,
    completedIterations,
  }
}

// ---------------------------------------------------------------------------
// Status display helpers
// ---------------------------------------------------------------------------

const STATUS_LABELS: Record<string, string> = {
  draft: 'Draft',
  designing: 'Clarifying',
  pending_user_review: 'Ready for Kickoff',
  approved: 'Approved',
  implementing: 'Implementing',
  self_test_passed: 'Self Test Passed',
  testing: 'Testing',
  pending_user_acceptance: 'Pending Acceptance',
  quality_check: 'Quality Check',
  done: 'Done',
}

export function statusLabel(status: string): string {
  return STATUS_LABELS[status] || status.replace(/_/g, ' ')
}

export function getIterationTitle(kind: RequirementKind, index: number): string {
  if (kind === 'product_mvp') return 'MVP Baseline'
  return `Change Request #${index}`
}

export function getNextAction(
  kind: RequirementKind,
  status: string,
): string {
  if (status === 'draft') return kind === 'product_mvp' ? 'Clarify MVP' : 'Clarify Change'
  if (status === 'designing') return kind === 'product_mvp' ? 'Clarify MVP' : 'Clarify Change'
  if (status === 'pending_user_review') return 'Start Kickoff'
  if (status === 'approved') return 'Start Delivery'
  if (status === 'pending_user_acceptance' || status === 'quality_check') return 'Review'
  if (status === 'implementing' || status === 'testing' || status === 'self_test_passed')
    return 'View Delivery'
  if (status === 'done') return 'Done'
  return status.replace(/_/g, ' ')
}
