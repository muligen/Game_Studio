import { Card } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import type { DeliveryTask } from '@/lib/api'

interface DeliveryTaskCardProps {
  task: DeliveryTask
  onStart?: () => void
  onRetry?: () => void
  onClick?: () => void
}

const STATUS_COLORS: Record<string, string> = {
  preview: 'bg-gray-100 text-gray-800',
  blocked: 'bg-red-100 text-red-800',
  ready: 'bg-green-100 text-green-800',
  in_progress: 'bg-blue-100 text-blue-800',
  review: 'bg-yellow-100 text-yellow-800',
  done: 'bg-emerald-100 text-emerald-800',
  failed: 'bg-red-100 text-red-800',
  cancelled: 'bg-gray-200 text-gray-600',
}

const AGENT_COLORS: Record<string, string> = {
  design: 'bg-purple-200',
  dev: 'bg-blue-200',
  qa: 'bg-orange-200',
  art: 'bg-pink-200',
  reviewer: 'bg-indigo-200',
  quality: 'bg-teal-200',
}

export function DeliveryTaskCard({ task, onStart, onRetry, onClick }: DeliveryTaskCardProps) {
  const canStart = task.status === 'ready' && onStart
  const canRetry = task.status === 'failed' && onRetry

  return (
    <Card
      className="p-4 hover:shadow-md transition-shadow cursor-pointer"
      onClick={onClick}
    >
      <div className="flex justify-between items-start mb-2">
        <span className="text-xs text-muted-foreground">{task.id}</span>
        <Badge className={AGENT_COLORS[task.owner_agent] || 'bg-gray-200'}>
          {task.owner_agent}
        </Badge>
      </div>
      <h3 className="font-medium mb-1">{task.title}</h3>
      <p className="text-sm text-muted-foreground mb-2 line-clamp-2">{task.description}</p>
      <div className="flex items-center justify-between mt-2">
        <Badge className={STATUS_COLORS[task.status] || STATUS_COLORS.ready}>
          {task.status.replace(/_/g, ' ')}
        </Badge>
        {task.depends_on_task_ids.length > 0 && (
          <span className="text-xs text-muted-foreground">
            {task.depends_on_task_ids.length} dep{task.depends_on_task_ids.length > 1 ? 's' : ''}
          </span>
        )}
      </div>
      {task.acceptance_criteria.length > 0 && (
        <div className="mt-2 text-xs text-muted-foreground">
          {task.acceptance_criteria.slice(0, 2).map((c, i) => (
            <div key={i} className="truncate">- {c}</div>
          ))}
        </div>
      )}
      {task.status === 'failed' && task.last_error && (
        <div className="mt-2 text-xs text-red-700 border-t pt-2">
          <div className="font-medium">Failed</div>
          <div className="line-clamp-3">{task.last_error}</div>
          {task.attempt_count > 0 && (
            <div className="mt-1 text-red-600">Attempt {task.attempt_count}</div>
          )}
        </div>
      )}
      {task.status === 'done' && task.output_artifact_ids.length > 0 && (
        <div className="mt-2 text-xs text-muted-foreground border-t pt-2">
          <div className="font-medium text-emerald-700">
            {task.output_artifact_ids.length} file{task.output_artifact_ids.length > 1 ? 's' : ''} changed
          </div>
          {task.output_artifact_ids.slice(0, 3).map((f) => (
            <div key={f} className="truncate font-mono">{f}</div>
          ))}
          {task.output_artifact_ids.length > 3 && (
            <div className="text-muted-foreground">
              +{task.output_artifact_ids.length - 3} more
            </div>
          )}
        </div>
      )}
      {canStart && (
        <button
          className="mt-2 text-xs text-blue-600 hover:underline"
          onClick={(e) => { e.stopPropagation(); onStart() }}
        >
          Start Agent Work
        </button>
      )}
      {canRetry && (
        <button
          className="mt-2 text-xs text-red-600 hover:underline"
          onClick={(e) => { e.stopPropagation(); onRetry() }}
        >
          Retry Agent Work
        </button>
      )}
    </Card>
  )
}
