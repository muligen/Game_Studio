import { RequirementCard } from './RequirementCard'

interface KanbanColumnProps {
  title: string
  requirements: Array<{
    id: string
    title: string
    status?: string
    priority?: string
    design_doc_id?: string | null
  }>
  onCardClick: (id: string) => void
  workspace: string
  onClarify?: (id: string, title: string) => void
}

export function KanbanColumn({ title, requirements, onCardClick, workspace, onClarify }: KanbanColumnProps) {
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
              design_doc_id={req.design_doc_id}
              workspace={workspace}
              onClick={() => onCardClick(req.id)}
              onClarify={onClarify ? () => onClarify(req.id, req.title) : undefined}
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
