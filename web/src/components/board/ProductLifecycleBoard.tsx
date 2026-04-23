import { RequirementCard } from './RequirementCard'
import {
  LIFECYCLE_COLUMNS,
  getLifecycleColumnKey,
  type RequirementKind,
} from '@/lib/product-workbench'

interface Requirement {
  id: string
  title: string
  status?: string
  priority?: string
  design_doc_id?: string | null
}

interface ProductLifecycleBoardProps {
  requirements: Requirement[]
  onCardClick: (id: string) => void
  workspace: string
  onClarify?: (id: string, title: string) => void
  requirementKinds: Map<string, RequirementKind>
}

export function ProductLifecycleBoard({
  requirements,
  onCardClick,
  workspace,
  onClarify,
  requirementKinds,
}: ProductLifecycleBoardProps) {
  const grouped = LIFECYCLE_COLUMNS.map((col) => ({
    ...col,
    cards: requirements.filter((req) => getLifecycleColumnKey(req.status || 'draft') === col.key),
  }))

  return (
    <div className="flex gap-4 overflow-x-auto pb-4">
      {grouped.map((col) => (
        <div key={col.key} className="flex-shrink-0 w-80">
          <div className="bg-gray-50 rounded-t-lg px-3 py-2 border-b">
            <h3 className="font-semibold text-sm uppercase text-gray-600">
              {col.title} ({col.cards.length})
            </h3>
          </div>
          <div className="space-y-3 pt-3">
            {col.cards.length === 0 ? (
              <p className="text-xs text-gray-400 px-3 italic">No items</p>
            ) : (
              col.cards.map((req) => (
                <RequirementCard
                  key={req.id}
                  id={req.id}
                  title={req.title}
                  status={req.status}
                  priority={req.priority}
                  design_doc_id={req.design_doc_id}
                  workspace={workspace}
                  kind={requirementKinds.get(req.id) || 'change_request'}
                  onClick={() => onCardClick(req.id)}
                  onClarify={onClarify ? () => onClarify(req.id, req.title) : undefined}
                />
              ))
            )}
          </div>
        </div>
      ))}
    </div>
  )
}
