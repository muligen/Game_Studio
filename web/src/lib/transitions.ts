import type { BugCard, TransitionRequirementRequest } from './api'

type RequirementStatus = TransitionRequirementRequest['next_status']
type BugStatus = BugCard['status']

const REQUIREMENT_TRANSITIONS: Record<RequirementStatus, readonly RequirementStatus[]> = {
  draft: ['designing'],
  designing: ['pending_user_review'],
  pending_user_review: ['approved', 'designing'],
  approved: ['implementing'],
  implementing: ['self_test_passed'],
  self_test_passed: ['testing'],
  testing: ['pending_user_acceptance', 'implementing'],
  pending_user_acceptance: ['quality_check', 'implementing'],
  quality_check: ['done', 'implementing'],
  done: [],
}

const BUG_TRANSITIONS: Record<BugStatus, readonly BugStatus[]> = {
  new: ['fixing'],
  fixing: ['fixed'],
  fixed: ['verifying'],
  verifying: ['closed', 'reopened', 'needs_user_decision'],
  reopened: ['fixing', 'needs_user_decision'],
  needs_user_decision: ['fixing', 'closed'],
  closed: [],
}

export function getRequirementTransitions(status: string): readonly RequirementStatus[] {
  return REQUIREMENT_TRANSITIONS[status as RequirementStatus] ?? []
}

export function getBugTransitions(status: string): readonly BugStatus[] {
  return BUG_TRANSITIONS[status as BugStatus] ?? []
}
