import { RequirementCard } from './RequirementCard'

interface KanbanColumnProps {
  title: string
  requirements: Array<{
    id: string
    title: string
    status?: string
    priority?: string
  }>
  onCardClick: (id: string) => void
  workspace: string
}

export function KanbanColumn({ title, requirements, onCardClick, workspace }: KanbanColumnProps) {
  return (
    <div className="flex-shrink-0 w-80">
      <div className="bg-gray-50 rounded-lg p-4">
        <h2 className="text-lg font-semibold mb-4 capitalize">{title}</h2>
        <div className="space-y-3">
          {requirements.map((req) => (
            <RequirementCard
              key={req.id}
              id={req.id}
              title={req.title}
              status={req.status}
              priority={req.priority}
              workspace={workspace}
              onClick={() => onCardClick(req.id)}
            />
          ))}
          {requirements.length === 0 && (
            <p className="text-sm text-gray-500 text-center py-4">No requirements</p>
          )}
        </div>
      </div>
    </div>
  )
}
