export interface MeetingTranscriptEvent {
  sequence: number
  agent_role: string
  node_name: string
  kind: 'llm'
  message: string
  prompt?: string | null
  context?: Record<string, unknown>
  reply?: unknown
}

export interface MeetingTranscriptResponse {
  id: string
  meeting_id: string
  requirement_id: string
  project_id?: string | null
  events: MeetingTranscriptEvent[]
  created_at?: string | null
  updated_at?: string | null
}

export interface DeliveryBoardItem {
  id: string
  status: string
  meeting_id: string
  requirement_id: string
  project_id: string
}

export interface DeliveryBoardResponse {
  plans: DeliveryBoardItem[]
  tasks: DeliveryBoardItem[]
  decision_gates: DeliveryBoardItem[]
}

const apiBaseUrl = process.env.E2E_API_URL ?? 'http://127.0.0.1:8000'
const workspace = process.env.E2E_WORKSPACE ?? '.'

async function fetchJson<T>(path: string): Promise<T> {
  const response = await fetch(`${apiBaseUrl}${path}`)
  if (!response.ok) {
    throw new Error(`Request failed ${response.status}: ${path}`)
  }

  return (await response.json()) as T
}

export async function fetchTranscript(meetingId: string): Promise<MeetingTranscriptResponse> {
  return fetchJson<MeetingTranscriptResponse>(
    `/api/meetings/${meetingId}/transcript?workspace=${encodeURIComponent(workspace)}`,
  )
}

export async function fetchDeliveryBoard(requirementId?: string): Promise<DeliveryBoardResponse> {
  const params = new URLSearchParams({ workspace })
  if (requirementId) {
    params.set('requirement_id', requirementId)
  }

  return fetchJson<DeliveryBoardResponse>(`/api/delivery-board?${params.toString()}`)
}
