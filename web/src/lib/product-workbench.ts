// web/src/lib/product-workbench.ts

import type { RequirementCard } from './api'

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export type RequirementKind = 'product_mvp' | 'change_request'
export type BaselineStatus = 'not_started' | 'defining_mvp' | 'active'

export interface ProductWorkbenchState {
  baselineStatus: BaselineStatus
  mvpRequirement: RequirementCard | null
  changeRequests: RequirementCard[]
  requirementKinds: Map<string, RequirementKind>
}

// ---------------------------------------------------------------------------
// Lifecycle column mapping
// ---------------------------------------------------------------------------

export interface LifecycleColumn {
  key: string
  title: string
  statuses: string[]
}

export const LIFECYCLE_COLUMNS: LifecycleColumn[] = [
  { key: 'product_setup', title: 'Product Setup', statuses: ['draft'] },
  { key: 'clarifying', title: 'Clarifying', statuses: ['designing'] },
  { key: 'ready_for_meeting', title: 'Ready for Meeting', statuses: ['pending_user_review'] },
  { key: 'decision_needed', title: 'Decision Needed', statuses: [] },
  { key: 'ready_for_delivery', title: 'Ready for Delivery', statuses: ['approved'] },
  { key: 'in_progress', title: 'In Progress', statuses: ['implementing', 'self_test_passed', 'testing'] },
  { key: 'review_acceptance', title: 'Review / Acceptance', statuses: ['pending_user_acceptance', 'quality_check'] },
  { key: 'done', title: 'Done', statuses: ['done'] },
]

// ---------------------------------------------------------------------------
// Next action labels
// ---------------------------------------------------------------------------

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
    return 'In Progress'
  if (status === 'done') return 'Done'
  return status.replace(/_/g, ' ')
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
      changeRequests: [],
      requirementKinds: new Map(),
    }
  }

  // TODO: Backend IDs are req_<uuid4().hex[:8]> — random, not time-ordered.
  // Sorting by ID is arbitrary here. Needs backend `created_at` field for correctness.
  const sorted = [...requirements].sort((a, b) => {
    return a.id.localeCompare(b.id)
  })

  const mvpRequirement = sorted[0]
  const mvpIsDone = mvpRequirement.status === 'done'
  const baselineStatus: BaselineStatus = mvpIsDone ? 'active' : 'defining_mvp'

  const kinds = new Map<string, RequirementKind>()
  kinds.set(mvpRequirement.id, 'product_mvp')

  const changeRequests: RequirementCard[] = []
  for (let i = 1; i < sorted.length; i++) {
    const req = sorted[i]
    if (baselineStatus === 'active') {
      kinds.set(req.id, 'change_request')
      changeRequests.push(req)
    } else {
      kinds.set(req.id, 'product_mvp')
    }
  }

  return {
    baselineStatus,
    mvpRequirement,
    changeRequests,
    requirementKinds: kinds,
  }
}

// ---------------------------------------------------------------------------
// Column assignment
// ---------------------------------------------------------------------------

export function getLifecycleColumnKey(status: string): string {
  for (const col of LIFECYCLE_COLUMNS) {
    if (col.statuses.includes(status)) return col.key
  }
  return 'product_setup'
}
