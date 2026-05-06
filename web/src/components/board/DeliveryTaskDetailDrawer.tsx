import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { deliveryApi } from '@/lib/api'
import type { DeliveryTask, DeliveryTaskEvent, DeliveryTaskSessionMessage } from '@/lib/api'
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'

interface DeliveryTaskDetailDrawerProps {
  task: DeliveryTask | null
  workspace: string
  open: boolean
  onOpenChange: (open: boolean) => void
}

type TabKey = 'overview' | 'events' | 'session' | 'artifacts'

const TABS: { key: TabKey; label: string }[] = [
  { key: 'overview', label: 'Overview' },
  { key: 'events', label: 'Events' },
  { key: 'session', label: 'Agent Session' },
  { key: 'artifacts', label: 'Artifacts' },
]

export function DeliveryTaskDetailDrawer({ task, workspace, open, onOpenChange }: DeliveryTaskDetailDrawerProps) {
  const [tab, setTab] = useState<TabKey>('overview')

  const eventsQuery = useQuery({
    queryKey: ['delivery-task-events', workspace, task?.id],
    queryFn: () => deliveryApi.getTaskEvents(workspace, task!.id),
    enabled: open && Boolean(task),
    refetchInterval: task?.status === 'in_progress' ? 2000 : false,
  })

  const sessionQuery = useQuery({
    queryKey: ['delivery-task-session', workspace, task?.id],
    queryFn: () => deliveryApi.getTaskSession(workspace, task!.id),
    enabled: open && Boolean(task) && tab === 'session',
    refetchInterval: task?.status === 'in_progress' && tab === 'session' ? 3000 : false,
  })

  if (!task) return null

  const events = eventsQuery.data?.events ?? []

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-2xl max-h-[80vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <span>{task.title}</span>
            <span className="text-xs text-muted-foreground font-normal">{task.id}</span>
          </DialogTitle>
        </DialogHeader>

        <div className="flex gap-1 border-b pb-1 mb-4">
          {TABS.map((t) => (
            <button
              key={t.key}
              className={`px-3 py-1.5 text-sm rounded-t ${
                tab === t.key
                  ? 'bg-gray-100 font-medium'
                  : 'text-muted-foreground hover:text-foreground'
              }`}
              onClick={() => setTab(t.key)}
            >
              {t.label}
            </button>
          ))}
        </div>

        {tab === 'overview' && <OverviewTab task={task} />}
        {tab === 'events' && <EventsTab events={events} isLoading={eventsQuery.isLoading} />}
        {tab === 'session' && (
          <SessionTab
            messages={sessionQuery.data?.messages ?? []}
            sessionId={sessionQuery.data?.session_id ?? null}
            isLoading={sessionQuery.isLoading}
          />
        )}
        {tab === 'artifacts' && <ArtifactsTab task={task} />}
      </DialogContent>
    </Dialog>
  )
}

function OverviewTab({ task }: { task: DeliveryTask }) {
  return (
    <div className="space-y-3 text-sm">
      <Row label="Owner Agent" value={task.owner_agent} />
      <Row label="Status" value={task.status.replace(/_/g, ' ')} />
      <Row label="Attempts" value={String(task.attempt_count)} />
      <Row label="Plan" value={task.plan_id} />
      <Row label="Requirement" value={task.requirement_id} />
      {task.description && (
        <div>
          <span className="text-muted-foreground">Description</span>
          <p className="mt-1">{task.description}</p>
        </div>
      )}
      {task.acceptance_criteria.length > 0 && (
        <div>
          <span className="text-muted-foreground">Acceptance Criteria</span>
          <ul className="mt-1 list-disc list-inside">
            {task.acceptance_criteria.map((c, i) => <li key={i}>{c}</li>)}
          </ul>
        </div>
      )}
      {task.depends_on_task_ids.length > 0 && (
        <div>
          <span className="text-muted-foreground">Dependencies</span>
          <div className="mt-1 flex flex-wrap gap-1">
            {task.depends_on_task_ids.map((id) => (
              <span key={id} className="text-xs bg-gray-100 px-2 py-0.5 rounded font-mono">{id}</span>
            ))}
          </div>
        </div>
      )}
      {task.last_error && (
        <div className="text-red-700 bg-red-50 p-2 rounded">
          <span className="font-medium">Last Error</span>
          <p className="mt-1 whitespace-pre-wrap text-xs">{task.last_error}</p>
        </div>
      )}
    </div>
  )
}

function EventsTab({ events, isLoading }: { events: DeliveryTaskEvent[]; isLoading: boolean }) {
  if (isLoading) return <p className="text-sm text-muted-foreground">Loading events...</p>
  if (events.length === 0) return <p className="text-sm text-muted-foreground">No events recorded yet.</p>

  return (
    <div className="space-y-2">
      {events.map((event) => (
        <div key={event.id} className="border rounded p-2 text-sm">
          <div className="flex justify-between items-start">
            <span className="font-mono text-xs bg-gray-100 px-1.5 py-0.5 rounded">
              {event.event_type.replace(/_/g, ' ')}
            </span>
            <span className="text-xs text-muted-foreground">
              {new Date(event.created_at).toLocaleTimeString()}
            </span>
          </div>
          <p className="mt-1">{event.message}</p>
          {Object.keys(event.metadata).length > 0 && (
            <details className="mt-1">
              <summary className="text-xs text-muted-foreground cursor-pointer">Metadata</summary>
              <pre className="text-xs bg-gray-50 p-2 mt-1 rounded overflow-x-auto">
                {JSON.stringify(event.metadata, null, 2)}
              </pre>
            </details>
          )}
        </div>
      ))}
    </div>
  )
}

function SessionTab({
  messages,
  sessionId,
  isLoading,
}: {
  messages: DeliveryTaskSessionMessage[]
  sessionId: string | null
  isLoading: boolean
}) {
  if (isLoading) return <p className="text-sm text-muted-foreground">Loading session...</p>
  if (messages.length === 0) {
    return (
      <p className="text-sm text-muted-foreground">
        No Claude session transcript is available yet.
      </p>
    )
  }

  return (
    <div className="space-y-2">
      {sessionId && (
        <p className="text-xs text-muted-foreground mb-2">Session: {sessionId}</p>
      )}
      {messages.map((msg, i) => (
        <div key={msg.uuid || i} className="border rounded p-2 text-sm">
          <span
            className={`text-xs font-mono px-1.5 py-0.5 rounded ${
              msg.role === 'assistant'
                ? 'bg-blue-100 text-blue-800'
                : msg.role === 'user'
                  ? 'bg-green-100 text-green-800'
                  : 'bg-gray-100 text-gray-800'
            }`}
          >
            {msg.role}
          </span>
          <p className="mt-1 whitespace-pre-wrap">{msg.content}</p>
          {msg.blocks.length > 0 && (
            <details className="mt-1">
              <summary className="text-xs text-muted-foreground cursor-pointer">Raw blocks</summary>
              <pre className="text-xs bg-gray-50 p-2 mt-1 rounded overflow-x-auto">
                {JSON.stringify(msg.blocks, null, 2)}
              </pre>
            </details>
          )}
        </div>
      ))}
    </div>
  )
}

function ArtifactsTab({ task }: { task: DeliveryTask }) {
  if (task.output_artifact_ids.length === 0) {
    return <p className="text-sm text-muted-foreground">No artifacts yet.</p>
  }

  return (
    <div className="space-y-1">
      <p className="text-sm text-muted-foreground mb-2">
        {task.output_artifact_ids.length} file{task.output_artifact_ids.length > 1 ? 's' : ''} changed
      </p>
      {task.output_artifact_ids.map((path) => (
        <div key={path} className="text-sm font-mono bg-gray-50 px-2 py-1 rounded">
          {path}
        </div>
      ))}
    </div>
  )
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex gap-2">
      <span className="text-muted-foreground w-28 shrink-0">{label}</span>
      <span className="font-mono text-xs">{value}</span>
    </div>
  )
}
