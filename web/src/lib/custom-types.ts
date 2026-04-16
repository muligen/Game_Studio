/**
 * Custom types not yet in the OpenAPI spec.
 * This file is safe from generate-types overwrites.
 */

// Bug Card types (not in OpenAPI spec yet)
export interface BugCard {
  id: string
  requirement_id: string
  title: string
  severity: 'low' | 'medium' | 'high' | 'critical'
  status: 'new' | 'fixing' | 'fixed' | 'verifying' | 'closed' | 'reopened' | 'needs_user_decision'
  reopen_count: number
  owner: string
  repro_steps: string[]
  notes: string[]
}

// Design Doc types (not in OpenAPI spec yet)
export interface DesignDoc {
  id: string
  title: string
  summary: string
  status: 'draft' | 'pending_user_review' | 'approved' | 'sent_back'
  core_rules: string[]
  acceptance_criteria: string[]
  open_questions: string[]
  requirement_id: string
  sent_back_reason?: string | null
  created_at: string
  updated_at: string
}
