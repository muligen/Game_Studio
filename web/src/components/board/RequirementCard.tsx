import { Card } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { TransitionMenu } from '@/components/common/TransitionMenu'
import { getRequirementTransitions } from '@/lib/transitions'
import { type RequirementKind, getNextAction } from '@/lib/product-workbench'

interface RequirementCardProps {
  id: string
  title: string
  status?: string
  priority?: string
  design_doc_id?: string | null
  workspace: string
  kind: RequirementKind
  onClick: () => void
  onClarify?: () => void
}

const KIND_CONFIG: Record<RequirementKind, { label: string; className: string }> = {
  product_mvp: { label: 'Product MVP', className: 'bg-indigo-100 text-indigo-800' },
  change_request: { label: 'Change Request', className: 'bg-amber-100 text-amber-800' },
}

const STATUS_COLORS: Record<string, string> = {
  draft: 'bg-gray-100 text-gray-800',
  designing: 'bg-blue-100 text-blue-800',
  pending_user_review: 'bg-yellow-100 text-yellow-800',
  approved: 'bg-green-100 text-green-800',
  implementing: 'bg-purple-100 text-purple-800',
  self_test_passed: 'bg-purple-100 text-purple-800',
  testing: 'bg-orange-100 text-orange-800',
  pending_user_acceptance: 'bg-amber-100 text-amber-800',
  quality_check: 'bg-amber-100 text-amber-800',
  done: 'bg-emerald-100 text-emerald-800',
}

const PRIORITY_COLORS: Record<string, string> = {
  low: 'bg-gray-200',
  medium: 'bg-yellow-200',
  high: 'bg-red-200',
}

export function RequirementCard({
  id,
  title,
  status,
  priority,
  design_doc_id,
  workspace,
  kind,
  onClick,
  onClarify,
}: RequirementCardProps) {
  const statusValue = status || 'draft'
  const priorityValue = priority || 'medium'
  const kindConfig = KIND_CONFIG[kind]
  const nextAction = getNextAction(kind, statusValue)

  return (
    <Card
      className="p-4 cursor-pointer hover:shadow-md transition-shadow"
      onClick={onClick}
    >
      <div className="flex justify-between items-start mb-2">
        <Badge className={kindConfig.className}>{kindConfig.label}</Badge>
        <Badge className={PRIORITY_COLORS[priorityValue]}>{priorityValue}</Badge>
      </div>
      <h3 className="font-medium mb-2">{title}</h3>
      <div className="flex items-center justify-between mt-2 gap-2">
        <div className="flex items-center gap-2 min-w-0">
          <Badge className={`text-xs ${STATUS_COLORS[statusValue] || STATUS_COLORS.draft}`}>
            {statusValue.replace(/_/g, ' ')}
          </Badge>
          <span className="text-xs font-medium text-blue-600 truncate">{nextAction}</span>
        </div>
        <TransitionMenu
          entityType="requirement"
          id={id}
          currentStatus={statusValue}
          workspace={workspace}
          allStatuses={getRequirementTransitions(statusValue)}
          designDocId={design_doc_id}
        />
      </div>
      {design_doc_id && (
        <a
          href={`/design-docs/${design_doc_id}`}
          className="text-xs text-blue-600 hover:underline mt-2 block"
          onClick={(e) => e.stopPropagation()}
        >
          View Design
        </a>
      )}
      {['draft', 'designing'].includes(statusValue) && onClarify && (
        <button
          className="text-xs text-blue-600 hover:underline mt-1 block"
          onClick={(e) => { e.stopPropagation(); onClarify() }}
        >
          Clarify
        </button>
      )}
    </Card>
  )
}
