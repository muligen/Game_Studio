import type { components } from './types'
import type { DesignDoc, BugCard } from './custom-types'

type Methods = 'get' | 'post' | 'put' | 'patch' | 'delete'

// Type aliases for convenience
export type RequirementCard = components['schemas']['RequirementCard']
export type TransitionRequirementRequest = components['schemas']['TransitionRequirementRequest']
export type MeetingMinutes = components['schemas']['MeetingMinutes']
export type { BugCard }
export type { DesignDoc }
export type DesignDocMutationResult = {
  design_doc: DesignDoc
  requirement: RequirementCard
}

// Base API client
const API_BASE = '/api'

export async function apiRequest(
  path: string,
  method: Methods,
  options?: Omit<RequestInit, 'body'> & {
    params?: Record<string, string | number | boolean>
    body?: BodyInit | Record<string, unknown> | FormData
    timeout?: number
  }
): Promise<unknown> {
  const { params, body, timeout, ...fetchOptions } = options || {}

  // Build query string from params
  const queryString = params
    ? '?' + new URLSearchParams(
        Object.entries(params).reduce((acc, [key, value]) => {
          if (value !== undefined && value !== null) {
            acc[key] = String(value)
          }
          return acc
        }, {} as Record<string, string>)
      ).toString()
    : ''

  // Prepare body - if it's a plain object, stringify it
  let finalBody: BodyInit | undefined
  let headers: Record<string, string> = { ...(fetchOptions.headers as Record<string, string> || {}) }

  if (body) {
    if (body instanceof FormData) {
      finalBody = body
      delete headers['Content-Type']
    } else if (typeof body === 'string') {
      finalBody = body
    } else {
      finalBody = JSON.stringify(body)
      headers['Content-Type'] = 'application/json'
    }
  }

  const controller = new AbortController()
  const timeoutId = timeout ? setTimeout(() => controller.abort(), timeout) : undefined

  try {
    const response = await fetch(`${API_BASE}${path}${queryString}`, {
      method: method.toUpperCase(),
      headers,
      ...fetchOptions,
      ...(finalBody && { body: finalBody }),
      signal: controller.signal,
    })

    if (!response.ok) {
      const error = await response.json().catch(() => ({ message: 'Unknown error' }))
      throw new Error(error.detail || error.message || 'API request failed')
    }

    return response.json()
  } catch (err) {
    if (err instanceof DOMException && err.name === 'AbortError') {
      throw new Error('Request timed out')
    }
    throw err
  } finally {
    if (timeoutId) clearTimeout(timeoutId)
  }
}

// Requirements API
export const requirementsApi = {
  list: (workspace: string): Promise<RequirementCard[]> =>
    apiRequest('/requirements', 'get', {
      params: { workspace },
    }) as Promise<RequirementCard[]>,

  create: (
    workspace: string,
    title: string,
    priority: 'low' | 'medium' | 'high' = 'medium'
  ): Promise<RequirementCard> => {
    return apiRequest('/requirements', 'post', {
      params: { workspace },
      body: JSON.stringify({ title, priority }),
      headers: {
        'Content-Type': 'application/json',
      },
    }) as Promise<RequirementCard>
  },

  get: (workspace: string, id: string): Promise<RequirementCard> =>
    apiRequest(`/requirements/${id}`, 'get', {
      params: { workspace },
    }) as Promise<RequirementCard>,

  transition: (
    workspace: string,
    id: string,
    nextStatus: TransitionRequirementRequest['next_status']
  ): Promise<RequirementCard> => {
    return apiRequest(`/requirements/${id}/transition`, 'post', {
      params: { workspace },
      body: JSON.stringify({ next_status: nextStatus }),
      headers: {
        'Content-Type': 'application/json',
      },
    }) as Promise<RequirementCard>
  },
} as const

// Design Docs API
export const designDocsApi = {
  list: (workspace: string): Promise<DesignDoc[]> =>
    apiRequest('/design-docs', 'get', {
      params: { workspace },
    }) as Promise<DesignDoc[]>,

  get: (workspace: string, id: string): Promise<DesignDoc> =>
    apiRequest(`/design-docs/${id}`, 'get', {
      params: { workspace },
    }) as Promise<DesignDoc>,

  update: (
    workspace: string,
    id: string,
    data: Partial<DesignDoc>
  ): Promise<DesignDoc> =>
    apiRequest(`/design-docs/${id}`, 'patch', {
      params: { workspace },
      body: JSON.stringify(data),
      headers: {
        'Content-Type': 'application/json',
      },
    }) as Promise<DesignDoc>,

  approve: (workspace: string, id: string): Promise<DesignDocMutationResult> =>
    apiRequest(`/design-docs/${id}/approve`, 'post', {
      params: { workspace },
    }) as Promise<DesignDocMutationResult>,

  sendBack: (workspace: string, id: string, reason: string): Promise<DesignDocMutationResult> => {
    return apiRequest(`/design-docs/${id}/send-back`, 'post', {
      params: { workspace },
      body: { reason },
    }) as Promise<DesignDocMutationResult>
  },
} as const

// Balance Tables API
export const balanceTablesApi = {
  list: (workspace: string): Promise<unknown[]> =>
    apiRequest('/balance-tables', 'get', {
      params: { workspace },
    }) as Promise<unknown[]>,

  get: (workspace: string, id: string): Promise<unknown> =>
    apiRequest(`/balance-tables/${id}`, 'get', {
      params: { workspace },
    }) as Promise<unknown>,

  update: (
    workspace: string,
    id: string,
    data: Record<string, unknown>
  ): Promise<unknown> =>
    apiRequest(`/balance-tables/${id}`, 'patch', {
      params: { workspace },
      body: JSON.stringify(data),
      headers: {
        'Content-Type': 'application/json',
      },
    }) as Promise<unknown>,
} as const

// Bugs API
export const bugsApi = {
  list: (workspace: string): Promise<BugCard[]> =>
    apiRequest('/bugs', 'get', {
      params: { workspace },
    }) as Promise<BugCard[]>,

  create: (
    workspace: string,
    requirementId: string,
    title: string,
    severity: BugCard['severity']
  ): Promise<BugCard> => {
    return apiRequest('/bugs', 'post', {
      params: { workspace },
      body: JSON.stringify({ requirement_id: requirementId, title, severity }),
      headers: {
        'Content-Type': 'application/json',
      },
    }) as Promise<BugCard>
  },

  transition: (
    workspace: string,
    id: string,
    nextStatus: BugCard['status']
  ): Promise<BugCard> => {
    return apiRequest(`/bugs/${id}/transition`, 'post', {
      params: { workspace },
      body: JSON.stringify({ next_status: nextStatus }),
      headers: {
        'Content-Type': 'application/json',
      },
    }) as Promise<BugCard>
  },
} as const

// Logs API
export const logsApi = {
  list: (workspace: string, limit: number = 100): Promise<unknown[]> =>
    apiRequest('/logs', 'get', {
      params: { workspace, limit },
    }) as Promise<unknown[]>,
} as const

// Workflows API
export const workflowsApi = {
  runDesign: (
    workspace: string,
    requirementId: string
  ): Promise<unknown> =>
    apiRequest('/workflows/run-design', 'post', {
      params: { workspace, requirement_id: requirementId },
    }) as Promise<unknown>,

  runDev: (workspace: string, requirementId: string): Promise<unknown> =>
    apiRequest('/workflows/run-dev', 'post', {
      params: { workspace, requirement_id: requirementId },
    }) as Promise<unknown>,

  runQa: (
    workspace: string,
    requirementId: string,
    fail: boolean = false
  ): Promise<unknown> =>
    apiRequest('/workflows/run-qa', 'post', {
      params: { workspace, requirement_id: requirementId, fail },
    }) as Promise<unknown>,
} as const

// Pool Status
export interface PoolStatus {
  max_workers: number
  active_count: number
  queued_count: number
  idle: boolean
  tasks: Array<{
    task_id: string
    agent_type: string
    requirement_id: string
    requirement_title: string
  }>
}

export const poolApi = {
  status: (): Promise<PoolStatus> =>
    apiRequest('/pool/status', 'get') as Promise<PoolStatus>,
} as const

// Delivery types
export interface DeliveryPlan {
  id: string
  meeting_id: string
  requirement_id: string
  project_id: string
  status: 'awaiting_user_decision' | 'active' | 'completed' | 'cancelled'
  task_ids: string[]
  decision_gate_id: string | null
  decision_resolution_version: number | null
  created_at: string
  updated_at: string
}

export interface DeliveryTask {
  id: string
  plan_id: string
  meeting_id: string
  requirement_id: string
  project_id: string
  title: string
  description: string
  owner_agent: string
  status: 'preview' | 'blocked' | 'ready' | 'in_progress' | 'review' | 'done' | 'cancelled'
  depends_on_task_ids: string[]
  execution_result_id: string | null
  output_artifact_ids: string[]
  acceptance_criteria: string[]
  meeting_snapshot: {
    meeting_title: string
    relevant_decisions: string[]
    relevant_consensus: string[]
    task_acceptance_notes: string[]
  } | null
  decision_resolution_version: number | null
  created_at: string
  updated_at: string
}

export interface GateItem {
  id: string
  question: string
  context: string
  options: string[]
  resolution: string | null
}

export interface KickoffDecisionGate {
  id: string
  plan_id: string
  meeting_id: string
  requirement_id: string
  project_id: string
  status: 'open' | 'resolved' | 'cancelled'
  resolution_version: number
  items: GateItem[]
  created_at: string
  updated_at: string
}

// Clarification Types
export interface ClarificationMessage {
  role: 'user' | 'assistant'
  content: string
  created_at: string
}

export interface MeetingContextDraft {
  summary: string
  goals: string[]
  constraints: string[]
  open_questions: string[]
  acceptance_criteria: string[]
  risks: string[]
  references: string[]
  validated_attendees: string[]
}

export interface ReadinessCheck {
  ready: boolean
  missing_fields: string[]
  notes: string[]
}

export interface ClarificationSession {
  id: string
  requirement_id: string
  status: string
  messages: ClarificationMessage[]
  meeting_context: MeetingContextDraft | null
  readiness: ReadinessCheck | null
  project_id: string | null
  created_at: string
  updated_at: string
}

export interface KickoffMeetingSnapshot {
  id: string
  title: string
  summary: string
  attendees: string[]
  consensus_points: string[]
  conflict_points: string[]
  pending_user_decisions: string[]
}

export interface KickoffResponse {
  task_id: string
  project_id: string
  status: string
}

export interface KickoffTaskStatus {
  id: string
  session_id: string
  requirement_id: string
  workspace: string
  project_id: string
  status: 'pending' | 'running' | 'completed' | 'failed'
  error: string | null
  meeting_result: KickoffMeetingResult | null
}

export interface KickoffMeetingResult {
  project_id: string
  requirement_id: string
  meeting_id: string
  status: string
  meeting: KickoffMeetingSnapshot
}

export interface DeliveryBoard {
  plans: DeliveryPlan[]
  tasks: DeliveryTask[]
  decision_gates: KickoffDecisionGate[]
}

export interface MeetingTranscriptEntry {
  id?: string
  sequence?: number
  role?: string
  speaker?: string
  agent_role?: string
  label?: string
  content?: string
  summary?: string
  message?: string
  node_name?: string
  kind?: string
  prompt?: string | null
  reply?: string | null
  raw_prompt?: string | null
  raw_reply?: string | null
  context?: Record<string, unknown> | null
  created_at?: string | null
  metadata?: Record<string, unknown> | null
}

export interface MeetingDetails extends MeetingMinutes {
  transcript?: MeetingTranscriptEntry[]
  transcript_entries?: MeetingTranscriptEntry[]
  raw_transcript?: MeetingTranscriptEntry[]
}

export interface MeetingTranscript {
  id: string
  meeting_id: string
  requirement_id: string
  project_id?: string | null
  events: MeetingTranscriptEntry[]
  created_at?: string | null
  updated_at?: string | null
}

// Clarifications API
export const clarificationsApi = {
  start: (workspace: string, requirementId: string): Promise<{ session: ClarificationSession }> =>
    apiRequest(`/clarifications/requirements/${requirementId}/session`, 'post', {
      params: { workspace },
    }) as Promise<{ session: ClarificationSession }>,

  sendMessage: (
    workspace: string,
    requirementId: string,
    sessionId: string,
    message: string,
  ): Promise<{ session: ClarificationSession; assistant_message: string }> =>
    apiRequest(`/clarifications/requirements/${requirementId}/messages`, 'post', {
      params: { workspace },
      body: JSON.stringify({ message, session_id: sessionId }),
      headers: { 'Content-Type': 'application/json' },
    }) as Promise<{ session: ClarificationSession; assistant_message: string }>,

  kickoff: (
    workspace: string,
    requirementId: string,
    sessionId: string,
  ): Promise<KickoffResponse> =>
    apiRequest(`/clarifications/requirements/${requirementId}/kickoff`, 'post', {
      params: { workspace },
      body: JSON.stringify({ session_id: sessionId }),
      headers: { 'Content-Type': 'application/json' },
    }) as Promise<KickoffResponse>,

  getKickoffTask: (
    workspace: string,
    taskId: string,
  ): Promise<KickoffTaskStatus> =>
    apiRequest(`/clarifications/kickoff-tasks/${taskId}`, 'get', {
      params: { workspace },
    }) as Promise<KickoffTaskStatus>,
}

export const meetingsApi = {
  get: (workspace: string, meetingId: string): Promise<MeetingDetails> =>
    apiRequest(`/meetings/${meetingId}`, 'get', {
      params: { workspace },
    }) as Promise<MeetingDetails>,

  getTranscript: (workspace: string, meetingId: string): Promise<MeetingTranscript> =>
    apiRequest(`/meetings/${meetingId}/transcript`, 'get', {
      params: { workspace },
    }) as Promise<MeetingTranscript>,
} as const

export const deliveryApi = {
  generatePlan: (
    workspace: string,
    meetingId: string,
    projectId: string,
  ): Promise<{ plan: DeliveryPlan; tasks: DeliveryTask[]; decision_gate: KickoffDecisionGate | null }> =>
    apiRequest(`/meetings/${meetingId}/delivery-plan`, 'post', {
      params: { workspace },
      body: { project_id: projectId },
      timeout: 180_000,
    }) as Promise<{ plan: DeliveryPlan; tasks: DeliveryTask[]; decision_gate: KickoffDecisionGate | null }>,

  listBoard: (workspace: string, requirementId?: string): Promise<DeliveryBoard> =>
    apiRequest('/delivery-board', 'get', {
      params: { workspace, ...(requirementId ? { requirement_id: requirementId } : {}) },
    }) as Promise<DeliveryBoard>,

  resolveGate: (
    workspace: string,
    gateId: string,
    resolutions: Record<string, string>,
  ): Promise<{ gate: KickoffDecisionGate; plan: DeliveryPlan }> =>
    apiRequest(`/kickoff-decision-gates/${gateId}/resolve`, 'post', {
      params: { workspace },
      body: { resolutions },
    }) as Promise<{ gate: KickoffDecisionGate; plan: DeliveryPlan }>,

  startTask: (
    workspace: string,
    taskId: string,
  ): Promise<DeliveryTask> =>
    apiRequest(`/delivery-tasks/${taskId}/start`, 'post', {
      params: { workspace },
      body: {},
    }) as Promise<DeliveryTask>,
} as const

export interface ProjectAgentSession {
  id: string
  project_id: string
  requirement_id: string
  agent: string
  session_id: string
  status: 'active' | 'expired'
  created_at: string
  last_used_at: string
}

export const sessionsApi = {
  listByProject: (projectId: string, workspace: string): Promise<{ project_id: string; sessions: ProjectAgentSession[] }> =>
    apiRequest(`/sessions/project/${projectId}`, 'get', {
      params: { workspace },
    }) as Promise<{ project_id: string; sessions: ProjectAgentSession[] }>,

  listAll: (workspace: string): Promise<{ sessions: ProjectAgentSession[] }> =>
    apiRequest('/sessions', 'get', {
      params: { workspace },
    }) as Promise<{ sessions: ProjectAgentSession[] }>,
} as const

export const agentsApi = {
  chat: (
    projectId: string,
    agent: string,
    request: { message: string },
    workspace: string,
  ): Promise<{ role: string; content: string }> =>
    apiRequest(`/agents/${projectId}/${agent}/chat`, 'post', {
      params: { workspace },
      body: request,
    }) as Promise<{ role: string; content: string }>,
} as const
