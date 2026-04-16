import type { components } from './types'
import type { DesignDoc, BugCard } from './custom-types'

type Methods = 'get' | 'post' | 'put' | 'patch' | 'delete'

// Type aliases for convenience
export type RequirementCard = components['schemas']['RequirementCard']
export type TransitionRequirementRequest = components['schemas']['TransitionRequirementRequest']
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
  }
): Promise<unknown> {
  const { params, body, ...fetchOptions } = options || {}

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
      // Don't set Content-Type for FormData - browser does it automatically with boundary
      delete headers['Content-Type']
    } else if (typeof body === 'string') {
      finalBody = body
    } else {
      finalBody = JSON.stringify(body)
      headers['Content-Type'] = 'application/json'
    }
  }

  const response = await fetch(`${API_BASE}${path}${queryString}`, {
    method: method.toUpperCase(),
    headers,
    ...fetchOptions,
    ...(finalBody && { body: finalBody }),
  })

  if (!response.ok) {
    const error = await response.json().catch(() => ({ message: 'Unknown error' }))
    throw new Error(error.detail || error.message || 'API request failed')
  }

  return response.json()
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
