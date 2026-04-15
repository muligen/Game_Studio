type Methods = 'get' | 'post' | 'put' | 'patch' | 'delete'

// Base API client
const API_BASE = '/api'

export async function apiRequest(
  path: string,
  method: Methods,
  options?: RequestInit & { params?: Record<string, any> }
): Promise<any> {
  const { params, ...fetchOptions } = options || {}

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

  const response = await fetch(`${API_BASE}${path}${queryString}`, {
    method: method.toUpperCase(),
    headers: {
      'Content-Type': 'application/json',
      ...fetchOptions.headers,
    },
    ...fetchOptions,
  })

  if (!response.ok) {
    const error = await response.json().catch(() => ({ message: 'Unknown error' }))
    throw new Error(error.detail || error.message || 'API request failed')
  }

  return response.json()
}

// Requirements API
export const requirementsApi = {
  list: (workspace: string) =>
    apiRequest('/requirements', 'get', {
      params: { workspace },
    }),

  create: (workspace: string, title: string, priority: string = 'medium') =>
    apiRequest('/requirements', 'post', {
      params: { workspace, title, priority },
    }),

  get: (workspace: string, id: string) =>
    apiRequest(`/requirements/${id}`, 'get', {
      params: { workspace },
    }),

  transition: (workspace: string, id: string, nextStatus: string) =>
    apiRequest(`/requirements/${id}/transition`, 'post', {
      params: { workspace, next_status: nextStatus },
    }),
} as const

// Design Docs API
export const designDocsApi = {
  list: (workspace: string) =>
    apiRequest('/design-docs', 'get', {
      params: { workspace },
    }),

  get: (workspace: string, id: string) =>
    apiRequest(`/design-docs/${id}`, 'get', {
      params: { workspace },
    }),

  update: (workspace: string, id: string, data: object) =>
    apiRequest(`/design-docs/${id}`, 'patch', {
      params: { workspace },
      body: JSON.stringify(data),
    }),

  approve: (workspace: string, id: string) =>
    apiRequest(`/design-docs/${id}/approve`, 'post', {
      params: { workspace },
    }),

  sendBack: (workspace: string, id: string, reason: string) =>
    apiRequest(`/design-docs/${id}/send-back`, 'post', {
      params: { workspace, reason },
    }),
} as const

// Balance Tables API
export const balanceTablesApi = {
  list: (workspace: string) =>
    apiRequest('/balance-tables', 'get', {
      params: { workspace },
    }),

  get: (workspace: string, id: string) =>
    apiRequest(`/balance-tables/${id}`, 'get', {
      params: { workspace },
    }),

  update: (workspace: string, id: string, data: object) =>
    apiRequest(`/balance-tables/${id}`, 'patch', {
      params: { workspace },
      body: JSON.stringify(data),
    }),
} as const

// Bugs API
export const bugsApi = {
  list: (workspace: string) =>
    apiRequest('/bugs', 'get', {
      params: { workspace },
    }),

  create: (
    workspace: string,
    requirementId: string,
    title: string,
    severity: string
  ) =>
    apiRequest('/bugs', 'post', {
      params: {
        workspace,
        requirement_id: requirementId,
        title,
        severity,
      },
    }),

  transition: (workspace: string, id: string, nextStatus: string) =>
    apiRequest(`/bugs/${id}/transition`, 'post', {
      params: { workspace, next_status: nextStatus },
    }),
} as const

// Logs API
export const logsApi = {
  list: (workspace: string, limit: number = 100) =>
    apiRequest('/logs', 'get', {
      params: { workspace, limit },
    }),
} as const

// Workflows API
export const workflowsApi = {
  runDesign: (workspace: string, requirementId: string) =>
    apiRequest('/workflows/run-design', 'post', {
      params: { workspace, requirement_id: requirementId },
    }),

  runDev: (workspace: string, requirementId: string) =>
    apiRequest('/workflows/run-dev', 'post', {
      params: { workspace, requirement_id: requirementId },
    }),

  runQa: (workspace: string, requirementId: string, fail: boolean = false) =>
    apiRequest('/workflows/run-qa', 'post', {
      params: { workspace, requirement_id: requirementId, fail },
    }),
} as const
